"""Detect conflicting facts before adding KG triples."""
from __future__ import annotations

from typing import Any, Protocol


class _KGLike(Protocol):
    def query_entity(self, entity: str, *, as_of: str | None = None) -> list[dict[str, Any]]: ...


def conflicting_objects_for_predicate(
    kg: _KGLike,
    subject: str,
    predicate: str,
    proposed_object: str,
) -> list[dict[str, Any]]:
    """
    If an active triple already has the same subject+predicate but a different object,
    return those rows (possible contradiction). Same object is not a conflict.
    """
    rows = kg.query_entity(subject, as_of=None)
    conflicts: list[dict[str, Any]] = []
    for t in rows:
        if t.get("p") != predicate:
            continue
        if t.get("valid_until"):
            continue
        o = str(t.get("o", ""))
        if o and o != proposed_object:
            conflicts.append(t)
    return conflicts
