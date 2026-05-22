from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from schemas import Goal

import action
import artifacts
import decision
import memory
import perception

MAX_ITERATIONS = 10

# ── logging ──────────────────────────────────────────────────────────────────
_logger = logging.getLogger("agent6")
_logger.setLevel(logging.DEBUG)
if not _logger.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_h)
    _logger.propagate = False

_W = 14  # label column width for aligned → arrows


def _log(msg: str) -> None:
    _logger.info(msg)


def _iter_banner(n: int) -> str:
    label = f" iter {n} "
    return f"\n── {label}{'─' * (56 - len(label))}"


def _lbl(label: str) -> str:
    """Left-pad label to fixed width so → arrows align."""
    return f"  {label:<{_W}}"


# ─────────────────────────────────────────────────────────────────────────────


def ensure_gateway() -> None:
    """Verify the LLM Gateway V3 is reachable."""
    try:
        httpx.get("http://localhost:8101/v1/capabilities", timeout=2).raise_for_status()
    except Exception as exc:
        raise RuntimeError(
            "LLM Gateway V3 is not running. Start it with: cd llm_gatewayV3 && bash run.sh"
        ) from exc


@asynccontextmanager
async def mcp_session() -> AsyncIterator[ClientSession]:
    """Async context manager that yields a connected MCP ClientSession."""
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).parent / "mcp_server.py")],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def load_tools(session: ClientSession) -> list[Any]:
    """Return the list of Tool objects from the MCP server."""
    result = await session.list_tools()
    return result.tools


def mcp_tools_for_decision(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    """Convert MCP Tool objects to the dict format expected by the decision layer."""
    return [
        {
            "name": t.name,
            "description": t.description or "",
            "input_schema": t.inputSchema,
        }
        for t in mcp_tools
    ]


def final_answer_from(history: list[dict[str, Any]]) -> str:
    """Extract the last answer entry from the run history."""
    for entry in reversed(history):
        if entry.get("kind") == "answer" and entry.get("text"):
            return str(entry["text"])
    for entry in reversed(history):
        if entry.get("result_descriptor"):
            return str(entry["result_descriptor"])
    return "No answer produced."


async def run(query: str) -> str:
    ensure_gateway()
    run_id = uuid.uuid4().hex[:8]
    history: list[dict[str, Any]] = []
    prior_goals: list[Goal] = []

    _log(f"[run {run_id}]  query  → \"{query[:100]}{'...' if len(query) > 100 else ''}\"")

    # Durable memory: classify the user's query so facts/preferences
    # in it survive into future runs.
    memory.remember(query, source="user_query", run_id=run_id)
    _log(f"[run {run_id}]  memory.remember  ← classified user query")

    async with mcp_session() as session:
        mcp_tools = await load_tools(session)
        tools = mcp_tools_for_decision(mcp_tools)
        _log(f"[run {run_id}]  MCP session ready — {len(mcp_tools)} tools loaded\n")

        for it in range(1, MAX_ITERATIONS + 1):
            _log(_iter_banner(it))

            # ── Memory read ──────────────────────────────────────────────────
            hits = memory.read(query, history)
            kinds = [h["kind"] for h in hits]
            art_count = sum(1 for h in hits if h.get("artifact_id") is not None)
            art_note = f"  ({art_count} with artifact)" if art_count else ""
            _log(f"{_lbl('memory.read')}→ {len(hits)} hit{'s' if len(hits) != 1 else ''}  "
                 f"{kinds}{art_note}")

            # ── Perception ───────────────────────────────────────────────────
            obs = perception.observe(query, hits, history, prior_goals, run_id)
            prior_goals = obs.goals
            done_count = sum(1 for g in obs.goals if g.done)
            _log(f"{_lbl('perception')}→ {len(obs.goals)} goal{'s' if len(obs.goals) != 1 else ''}"
                 f"  ({done_count} done, {len(obs.goals) - done_count} todo)")
            for g in obs.goals:
                status = "DONE" if g.done else "TODO"
                art = f"  attach={g.attach_artifact_id}" if g.attach_artifact_id else ""
                _log(f"    {g.id} [{status}]{art}: {g.text[:80]}")

            if obs.all_done:
                _log(f"  {'─' * 54}")
                _log(f"  all goals done — loop complete")
                break

            goal = obs.next_unfinished()

            # ── Artifact attachment ──────────────────────────────────────────
            attached: list[tuple[str, bytes]] = []
            if goal.attach_artifact_id and artifacts.exists(goal.attach_artifact_id):
                data = artifacts.get_bytes(goal.attach_artifact_id)
                attached.append((goal.attach_artifact_id, data))
                _log(f"{_lbl('attach')}→ artifact {goal.attach_artifact_id}"
                     f"  ({len(data):,} bytes) → {goal.id}")

            # ── Decision ─────────────────────────────────────────────────────
            out = decision.next_step(goal, hits, attached, history, tools)
            if out.is_answer:
                _log(f"{_lbl('decision')}→ ANSWER  ({len(out.answer):,} chars)"
                     f"  [goal {goal.id}]")
            else:
                args_preview = ", ".join(
                    f"{k}='{str(v)[:40]}'" for k, v in out.tool_call.arguments.items()
                )
                _log(f"{_lbl('decision')}→ TOOL {out.tool_call.name}({args_preview})"
                     f"  [goal {goal.id}]")

            if out.is_answer:
                history.append({"iter": it, "kind": "answer",
                                "goal_id": goal.id, "text": out.answer})
                continue

            # ── Action ───────────────────────────────────────────────────────
            result_text, art_id = await action.execute(session, out.tool_call)
            if art_id is not None:
                _log(f"{_lbl('action')}→ artifact {art_id}"
                     f"  ({len(artifacts.get_bytes(art_id)):,} bytes)")
            else:
                _log(f"{_lbl('action')}→ inline  ({len(result_text):,} chars)")

            # ── Memory record ────────────────────────────────────────────────
            memory.record_outcome(
                tool_call=out.tool_call,
                result_text=result_text,
                artifact_id=art_id,
                run_id=run_id,
                goal_id=goal.id,
            )
            art_note = f"  → artifact {art_id}" if art_id is not None else ""
            _log(f"{_lbl('memory.record')}→ tool_outcome stored{art_note}")

            history.append({"iter": it, "kind": "action",
                            "goal_id": goal.id, "tool": out.tool_call.name,
                            "arguments": out.tool_call.arguments,
                            "result_descriptor": result_text[:300],
                            "artifact_id": art_id})

    answer = final_answer_from(history)
    _log(f"\n[run {run_id}]  done — {min(it, MAX_ITERATIONS)} iteration{'s' if it != 1 else ''}"
         f", answer {len(answer):,} chars")
    return answer


if __name__ == "__main__":
    import sys as _sys
    _query = " ".join(_sys.argv[1:]) or "What time is it in Tokyo?"
    print(asyncio.run(run(_query)))
