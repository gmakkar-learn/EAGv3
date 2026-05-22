"""Decision layer — given a goal, pick the next action or produce an answer."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

_gw = str(Path(__file__).parent / "llm_gatewayV3")
if _gw not in sys.path:
    sys.path.append(_gw)
from client import LLM  # noqa: E402

from schemas import DecisionOutput, Goal, ToolCall

# When attached artifact is present AND the goal asks for synthesis/extraction,
# force the model to answer (no tool calls). Goals that need to FETCH new content
# (fetch, read URLs, search) are excluded — attachment is just context there.
_ANSWER_FORCE_KEYWORDS = {
    "extract", "tell", "list", "compare", "summarize", "summarise",
    "synthesize", "synthesise", "agree", "advise", "give", "provide",
    "show", "explain", "what", "when", "who", "which", "how many",
    "birth", "death", "contributions", "recommend", "select", "decide",
    "analyse", "analyze", "review", "consolidate", "combine",
}

_SYSTEM = """\
You are Decision, an AI agent that selects the next action for a single bounded goal.

RULES:
1. Respond with EXACTLY ONE of: a substantive final answer (plain text), OR a single tool call. Never both.
2. Artifact IDs are integers like "0", "1", "2". They are internal memory handles — do NOT pass them as file paths or URLs to any tool. If attached artifact content is provided below, use it directly.
3. When the goal asks for extraction, listing, comparison, synthesis, or selection, your answer MUST be substantive: at least 3 complete sentences, or a numbered/bulleted list of items. Never return meta-answers like "the page has been fetched" or "I found some results."
4. Do not repeat a tool call that already appears in the run history with the same arguments.
5. If attached artifact content is present, use it to answer the goal directly — do not re-fetch.\
"""


def _fmt_hits(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return "(none)"
    lines = []
    for h in hits:
        art = h.get("artifact_id")
        art_str = f" [artifact_id={art}]" if art is not None else ""
        lines.append(f"  [{h['kind']}]{art_str} {h['descriptor']}")
        val = h.get("value", {})
        if val:
            preview = str(val)[:120]
            lines.append(f"    value: {preview}")
    return "\n".join(lines)


def _fmt_history(history: list[dict[str, Any]]) -> str:
    if not history:
        return "(none)"
    lines = []
    for e in history[-6:]:
        kind = e.get("kind", "?")
        if kind == "action":
            lines.append(
                f"  TOOL {e.get('tool','?')}({e.get('arguments',{})}) → {e.get('result_descriptor','')[:150]}"
            )
        elif kind == "answer":
            lines.append(f"  ANSWER: {str(e.get('text',''))[:200]}")
    return "\n".join(lines) if lines else "(none)"


def _fmt_attached(attached: list[tuple[str, bytes]]) -> str:
    if not attached:
        return ""
    parts = []
    for art_id, data in attached:
        text = data.decode("utf-8", errors="replace")
        parts.append(f"=== ARTIFACT {art_id} ({len(data)} bytes) ===\n{text[:25000]}")
    return "\n".join(parts)


def next_step(
    goal: Goal,
    hits: list[dict[str, Any]],
    attached: list[tuple[str, bytes]],
    history: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> DecisionOutput:
    """Return a DecisionOutput with either an answer or a tool call."""
    has_attached = bool(attached)

    # Force answer-only when artifact is attached AND goal is clearly synthesis.
    # Goals that still need to FETCH new URLs keep tool_choice="auto".
    goal_words = set(goal.text.lower().split())
    force_answer = has_attached and bool(goal_words & _ANSWER_FORCE_KEYWORDS)

    if has_attached:
        artifact_section = _fmt_attached(attached)
        if force_answer:
            user_content = (
                f"The following content has already been fetched for you.\n"
                f"Read it carefully and use it to answer the goal. Do NOT call any tool.\n\n"
                f"{artifact_section}\n\n"
                f"CURRENT GOAL: {goal.text}\n\n"
                f"RELEVANT MEMORY:\n{_fmt_hits(hits)}\n\n"
                f"RECENT HISTORY:\n{_fmt_history(history)}"
            )
        else:
            user_content = (
                f"CURRENT GOAL: {goal.text}\n\n"
                f"CONTEXT (already fetched — use as background):\n{artifact_section}\n\n"
                f"RELEVANT MEMORY:\n{_fmt_hits(hits)}\n\n"
                f"RECENT HISTORY:\n{_fmt_history(history)}"
            )
    else:
        user_content = (
            f"CURRENT GOAL: {goal.text}\n\n"
            f"RELEVANT MEMORY:\n{_fmt_hits(hits)}\n\n"
            f"RECENT HISTORY:\n{_fmt_history(history)}"
        )

    active_tools = None if force_answer else tools
    active_tool_choice = None if force_answer else "auto"

    llm = LLM()
    for _attempt in range(3):
        try:
            resp = llm.chat(
                messages=[{"role": "user", "content": user_content}],
                system=_SYSTEM,
                auto_route="decision",
                tools=active_tools,
                tool_choice=active_tool_choice,
                max_tokens=2048,
                temperature=0.7,
            )
            break
        except Exception as e:
            if _attempt < 2 and ("502" in str(e) or "503" in str(e) or "429" in str(e)):
                time.sleep(3 * (2 ** _attempt))
                continue
            raise

    gateway_tool_calls = resp.get("tool_calls", [])
    if gateway_tool_calls:
        tc = gateway_tool_calls[0]
        return DecisionOutput(
            answer=None,
            tool_call=ToolCall(name=tc["name"], arguments=tc.get("arguments", {})),
        )

    return DecisionOutput(answer=resp.get("text", ""), tool_call=None)
