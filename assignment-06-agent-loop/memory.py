"""Durable memory layer — classify, store, and retrieve facts across runs."""
from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_gw = str(Path(__file__).parent / "llm_gatewayV3")
if _gw not in sys.path:
    sys.path.append(_gw)
from client import LLM  # noqa: E402

from schemas import MemoryItem, ToolCall

_MEMORY_PATH = Path(__file__).parent / "state" / "memory.json"

_STOPWORDS = {
    "a", "an", "the", "is", "it", "in", "of", "to", "for", "and", "or",
    "that", "this", "be", "was", "are", "with", "as", "at", "by", "from",
    "on", "my", "me", "i", "you", "your", "he", "she", "they", "we",
    "will", "would", "could", "should", "have", "has", "had", "do", "does",
    "did", "not", "no", "if", "but", "so", "what", "when", "where", "how",
    "which", "who", "about", "up", "out", "get", "give", "can", "also",
    "just", "then", "now", "more", "some", "any", "all", "been", "here",
    "there", "were", "its", "into", "use", "used", "using",
}

# Gemini-safe schema for memory classification
_CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["fact", "preference"]},
                    "value": {
                        "type": "object",
                        "properties": {
                            "entity": {"type": "string"},
                            "attribute": {"type": "string"},
                            "detail": {"type": "string"},
                        },
                        "required": ["entity", "attribute", "detail"],
                    },
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "descriptor": {"type": "string"},
                },
                "required": ["kind", "value", "keywords", "descriptor"],
            },
        }
    },
    "required": ["items"],
}


def _load() -> list[MemoryItem]:
    if not _MEMORY_PATH.exists():
        return []
    try:
        raw = json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
        return [MemoryItem(**item) for item in raw]
    except Exception:
        return []


def _save(items: list[MemoryItem]) -> None:
    _MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MEMORY_PATH.write_text(
        json.dumps([item.model_dump(mode="json") for item in items], indent=2),
        encoding="utf-8",
    )


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 1}


def remember(text: str, *, source: str, run_id: str) -> None:
    """Classify and persist facts/preferences found in text. No-op if nothing memorable."""
    llm = LLM()
    try:
        resp = llm.chat(
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Extract any facts or personal preferences a personal assistant should remember "
                        "for future conversations. Only extract durable information (names, dates, locations, "
                        "personal preferences). If the text is just a task or question, return items=[].\n\n"
                        f"Text: {text}"
                    ),
                }
            ],
            provider="g",
            temperature=0.3,
            max_tokens=1024,
            response_format={
                "type": "json_schema",
                "schema": _CLASSIFY_SCHEMA,
                "name": "MemoryClassification",
            },
        )
        parsed = resp.get("parsed") or json.loads(resp.get("text", "{}"))
        items_data = parsed.get("items", [])
    except Exception:
        return  # graceful degradation

    if not items_data:
        return

    existing = _load()
    now = datetime.now(timezone.utc)
    for item in items_data:
        mem = MemoryItem(
            id=uuid.uuid4().hex[:8],
            kind=item["kind"],
            keywords=[k.lower() for k in item.get("keywords", [])],
            descriptor=item.get("descriptor", ""),
            value=item.get("value", {}),
            artifact_id=None,
            source=source,
            run_id=run_id,
            goal_id=None,
            confidence=0.85,
            created_at=now,
        )
        existing.append(mem)
    _save(existing)


def read(query: str, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keyword-search memory and return the top matching items as dicts."""
    items = _load()
    if not items:
        return []

    # Build query token set from the query + recent history text
    query_tokens = _tokenize(query)
    for entry in history[-4:]:
        query_tokens |= _tokenize(str(entry.get("result_descriptor", "")))
        query_tokens |= _tokenize(str(entry.get("text", "")))
        query_tokens |= _tokenize(str(entry.get("tool", "")))
        for v in entry.get("arguments", {}).values():
            query_tokens |= _tokenize(str(v)[:100])

    scored: list[tuple[int, MemoryItem]] = []
    for item in items:
        item_tokens = set(item.keywords)
        overlap = len(query_tokens & item_tokens)
        if overlap > 0:
            scored.append((overlap, item))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        {
            "kind": item.kind,
            "descriptor": item.descriptor,
            "value": item.value,
            "keywords": item.keywords,
            "artifact_id": item.artifact_id,
        }
        for _, item in scored[:8]
    ]


def record_outcome(
    *,
    tool_call: ToolCall,
    result_text: str,
    artifact_id: str | None,
    run_id: str,
    goal_id: str | None,
) -> None:
    """Persist the outcome of a tool call as a tool_outcome memory item."""
    kw_tokens = _tokenize(tool_call.name)
    for arg_val in tool_call.arguments.values():
        kw_tokens |= _tokenize(str(arg_val)[:300])
    kw_tokens |= _tokenize(result_text[:400])

    descriptor = (
        f"{tool_call.name}("
        + ", ".join(f"{k}={str(v)[:40]}" for k, v in tool_call.arguments.items())
        + ")"
    )
    if artifact_id is not None:
        descriptor += f" → artifact {artifact_id}"

    mem = MemoryItem(
        id=uuid.uuid4().hex[:8],
        kind="tool_outcome",
        keywords=list(kw_tokens)[:24],
        descriptor=descriptor,
        value={
            "tool": tool_call.name,
            "arguments": tool_call.arguments,
            "result_preview": result_text[:600],
            "artifact_id": artifact_id,
        },
        artifact_id=artifact_id,
        source="action",
        run_id=run_id,
        goal_id=goal_id,
        confidence=1.0,
        created_at=datetime.now(timezone.utc),
    )
    existing = _load()
    existing.append(mem)
    _save(existing)
