"""Perception layer — orchestrator that converts context into a structured Observation."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

_gw = str(Path(__file__).parent / "llm_gatewayV3")
if _gw not in sys.path:
    sys.path.append(_gw)
from client import LLM  # noqa: E402

from schemas import Goal, Observation

# Synthesis keywords that trigger force-attach
_SYNTHESIS_KEYWORDS = {
    "synthesize", "synthesise", "extract", "list", "compare", "decide",
    "summarize", "summarise", "agree", "advise", "analyse", "analyze",
    "findings", "review", "combine", "consolidate",
}

# Gemini-safe schema for Observation output
_OBSERVATION_SCHEMA = {
    "type": "object",
    "properties": {
        "goals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "done": {"type": "boolean"},
                    "attach_artifact_id": {"type": "string"},
                },
                "required": ["id", "text", "done"],
            },
        }
    },
    "required": ["goals"],
}

_SYSTEM = """\
You are Perception, the orchestrator of a multi-step AI agent.

Think step by step through the context before producing the goal list. Follow the four steps below in order.

STEP 1 — CLASSIFY GOAL TYPES (when decomposing, assign one type to each goal):
  FETCH    = retrieve content from a URL or web search
  EXTRACT  = parse specific information out of already-fetched content
  COMPUTE  = calculate, look up a date/time, or derive a value
  SYNTHESIZE = combine or compare information from multiple sources
  ANSWER   = respond directly from memory or context, no tool needed
  Use the type to guide done-checking: FETCH is done when history shows the resource was retrieved;
  EXTRACT/SYNTHESIZE are done when an ANSWER entry in history contains the extracted content;
  COMPUTE/ANSWER are done when an ANSWER entry addresses the question.

STEP 2 — DECOMPOSE OR PRESERVE:
  FIRST CALL (prior_goals empty): Break the query into a minimal ordered list of short imperative goals.
    Use IDs g0, g1, g2... Each goal is a single bounded task.
    FALLBACK: If the query is a simple question requiring no multi-step work, create exactly one goal
    whose text is the question itself (e.g. for "When is mom's birthday?" → "Answer: When is mom's birthday?").
    Never use generic text like "Answer the user's query directly" — always embed the actual query.
  SUBSEQUENT CALLS: Preserve all prior goals exactly — same id, same text, same order.
    Only update done flags and attach_artifact_id. Do NOT add, reorder, or rephrase goals.

STEP 3 — MARK DONE (apply to each goal in order):
  Set done=true ONLY when RUN HISTORY contains an ANSWER or tool result that explicitly satisfies it.
  - Memory hits are input context only — they do NOT count as completed results.
  - On the first call (history is always empty), every goal MUST be done=false.
  - When uncertain whether a history entry fully satisfies a goal, keep done=false (safer default).
  - Once done=true, always keep it true in all later calls.

STEP 4 — ATTACH ARTIFACTS (first unfinished goal only):
  If the goal is type EXTRACT or SYNTHESIZE AND memory hits contain an artifact_id, set
  attach_artifact_id to that artifact_id (use the most recent if there are multiple).
  For other goal types, only attach if the goal explicitly needs the fetched content.
  NEVER fabricate artifact IDs — only use integer strings explicitly shown in MEMORY HITS.

SELF-CHECK before outputting:
  a) Every done=true goal has an explicit supporting entry in RUN HISTORY. Unsure → false.
  b) Every attach_artifact_id is an exact integer string from MEMORY HITS. Unsure → omit it.
  c) On subsequent calls, goal IDs and texts match prior_goals exactly.
  d) No goals were added or reordered after the first call.\
"""


def _fmt_hits(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return "  (none)"
    lines = []
    for h in hits:
        art = h.get("artifact_id")
        art_str = f"  artifact_id={art}" if art is not None else ""
        lines.append(f"  [{h['kind']}]{art_str} | {h['descriptor']}")
    return "\n".join(lines)


def _fmt_history(history: list[dict[str, Any]]) -> str:
    if not history:
        return "  (none)"
    lines = []
    for e in history[-8:]:
        kind = e.get("kind", "?")
        if kind == "action":
            lines.append(
                f"  iter {e.get('iter','?')}: TOOL {e.get('tool','?')} → {e.get('result_descriptor','')[:120]}"
            )
        elif kind == "answer":
            lines.append(
                f"  iter {e.get('iter','?')}: ANSWER (goal {e.get('goal_id','?')}): {str(e.get('text',''))[:150]}"
            )
    return "\n".join(lines) if lines else "  (none)"


def _fmt_prior(prior: list[Goal]) -> str:
    if not prior:
        return "  (none — decompose the query now)"
    lines = []
    for g in prior:
        status = "DONE" if g.done else "TODO"
        art = f"  attach={g.attach_artifact_id}" if g.attach_artifact_id else ""
        lines.append(f"  {g.id} [{status}]{art} | {g.text}")
    return "\n".join(lines)


def observe(
    query: str,
    hits: list[dict[str, Any]],
    history: list[dict[str, Any]],
    prior_goals: list[Goal],
    run_id: str,
) -> Observation:
    """Produce a structured Observation from the current context."""
    user_msg = (
        f"USER QUERY:\n  {query}\n\n"
        f"MEMORY HITS:\n{_fmt_hits(hits)}\n\n"
        f"RUN HISTORY:\n{_fmt_history(history)}\n\n"
        f"PRIOR GOALS:\n{_fmt_prior(prior_goals)}"
    )

    llm = LLM()
    for _attempt in range(3):
        try:
            resp = llm.chat(
                messages=[{"role": "user", "content": user_msg}],
                system=_SYSTEM,
                provider="g",
                temperature=1.0,
                max_tokens=1024,
                response_format={
                    "type": "json_schema",
                    "schema": _OBSERVATION_SCHEMA,
                    "name": "Observation",
                },
            )
            break
        except Exception as e:
            if _attempt < 2 and ("502" in str(e) or "503" in str(e) or "429" in str(e)):
                time.sleep(3 * (2 ** _attempt))
                continue
            raise

    raw = resp.get("parsed") or json.loads(resp.get("text", "{}"))
    goals = [Goal(**g) for g in raw.get("goals", [])]

    # --- force-attach safety net ---
    # If the first unfinished goal has synthesis keywords AND a hit has an artifact,
    # ensure attach_artifact_id is set (guards against the LLM forgetting).
    artifact_hits = [h for h in hits if h.get("artifact_id") is not None]
    if artifact_hits:
        for g in goals:
            if not g.done:
                goal_words = set(g.text.lower().split())
                if goal_words & _SYNTHESIS_KEYWORDS and g.attach_artifact_id is None:
                    # Use the last (most recent) artifact in hits
                    g.attach_artifact_id = artifact_hits[-1]["artifact_id"]
                break  # only the first unfinished goal

    return Observation(goals=goals)
