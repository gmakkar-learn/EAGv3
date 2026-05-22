from __future__ import annotations

import asyncio
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

    # Durable memory: classify the user's query so facts/preferences
    # in it survive into future runs.
    memory.remember(query, source="user_query", run_id=run_id)

    async with mcp_session() as session:
        mcp_tools = await load_tools(session)
        tools = mcp_tools_for_decision(mcp_tools)

        for it in range(1, MAX_ITERATIONS + 1):
            hits = memory.read(query, history)
            obs = perception.observe(query, hits, history, prior_goals, run_id)
            prior_goals = obs.goals
            if obs.all_done:
                break

            goal = obs.next_unfinished()
            attached: list[tuple[str, bytes]] = []
            if goal.attach_artifact_id and artifacts.exists(goal.attach_artifact_id):
                attached.append((
                    goal.attach_artifact_id,
                    artifacts.get_bytes(goal.attach_artifact_id),
                ))

            out = decision.next_step(goal, hits, attached, history, tools)

            if out.is_answer:
                history.append({"iter": it, "kind": "answer",
                                "goal_id": goal.id, "text": out.answer})
                continue

            result_text, art_id = await action.execute(session, out.tool_call)
            memory.record_outcome(
                tool_call=out.tool_call,
                result_text=result_text,
                artifact_id=art_id,
                run_id=run_id,
                goal_id=goal.id,
            )
            history.append({"iter": it, "kind": "action",
                            "goal_id": goal.id, "tool": out.tool_call.name,
                            "arguments": out.tool_call.arguments,
                            "result_descriptor": result_text[:300],
                            "artifact_id": art_id})

    return final_answer_from(history)


if __name__ == "__main__":
    import sys as _sys
    _query = " ".join(_sys.argv[1:]) or "What time is it in Tokyo?"
    print(asyncio.run(run(_query)))
