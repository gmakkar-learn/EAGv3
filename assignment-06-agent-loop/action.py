"""Action layer — execute a ToolCall against an active MCP session."""
from __future__ import annotations

from mcp import ClientSession

import artifacts
from schemas import ToolCall

ARTIFACT_THRESHOLD_BYTES = 4096


async def execute(
    session: ClientSession,
    tool_call: ToolCall,
) -> tuple[str, str | None]:
    """Run the tool and return (result_text, artifact_id | None)."""
    # Guard: reject internal artifact IDs passed as tool arguments
    for key, val in tool_call.arguments.items():
        if isinstance(val, str) and artifacts.exists(val):
            return (
                f"Error: '{val}' is an internal artifact ID, not a file path or URL. "
                "Do not pass artifact IDs to tools — the content is available via ATTACHED ARTIFACTS.",
                None,
            )

    # Dispatch the MCP call
    result = await session.call_tool(tool_call.name, arguments=tool_call.arguments)

    # Collapse all content blocks into a single string
    parts: list[str] = []
    for block in result.content:
        if hasattr(block, "text"):
            parts.append(block.text)
        elif isinstance(block, dict):
            parts.append(block.get("text", str(block)))
        else:
            parts.append(str(block))
    text = "\n".join(parts)

    # Store large payloads in the artifact store
    data = text.encode("utf-8")
    if len(data) > ARTIFACT_THRESHOLD_BYTES:
        art_id = artifacts.put(data)
        preview = text[:200].replace("\n", " ")
        descriptor = f"[artifact {art_id}, {len(data)} bytes] preview: {preview}..."
        return descriptor, art_id

    return text, None
