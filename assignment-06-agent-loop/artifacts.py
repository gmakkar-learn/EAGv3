"""In-memory artifact store — persist large tool payloads by auto-increment ID."""
from __future__ import annotations

_store: dict[str, bytes] = {}
_counter: list[int] = [0]


def put(data: bytes) -> str:
    """Store bytes and return a new integer string ID."""
    art_id = str(_counter[0])
    _counter[0] += 1
    _store[art_id] = data
    return art_id


def exists(artifact_id: str) -> bool:
    return artifact_id in _store


def get_bytes(artifact_id: str) -> bytes:
    return _store[artifact_id]
