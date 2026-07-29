"""Detect conflicting facts before adding KG triples."""
from __future__ import annotations

from typing import Any, Protocol

# Structural rebuild predicates are multi-valued (many targets per subject).
MULTI_VALUED_PREDICATES = frozenset(
    {
        "mentions",
        "links_to",
        "tagged",
        "curated_by",
    }
)


class _KGLike(Protocol):
    def query_entity(self, entity: str, *, as_of: str | None = None) -> list[dict[str, Any]]: ...


def conflicting_objects_for_predicate(
    kg: _KGLike,
    subject: str,
    predicate: str,
    proposed_object: str,
    cfg: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    If an active triple already has the same subject+predicate but a different object,
    return those rows (possible contradiction). Same object is not a conflict.
    Multi-valued structural predicates (mentions/links_to/…) never conflict.
    """
    if predicate in MULTI_VALUED_PREDICATES:
        return []
    from lib.entity_aliases import canonicalize_entity

    subject = canonicalize_entity(subject, cfg)
    proposed_object = canonicalize_entity(proposed_object, cfg)
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


def find_predicate_conflicts(triples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Scan all triples for active (s,p) pairs with multiple distinct objects.
    Skips multi-valued structural predicates.
    Returns rows: {subject, predicate, objects: [...], triples: [...]}
    """
    active: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for t in triples:
        if t.get("valid_until"):
            continue
        s, p = str(t.get("s", "")), str(t.get("p", ""))
        if not s or not p or p in MULTI_VALUED_PREDICATES:
            continue
        active.setdefault((s, p), []).append(t)
    out: list[dict[str, Any]] = []
    for (s, p), rows in sorted(active.items()):
        objs = sorted({str(r.get("o", "")) for r in rows if r.get("o")})
        if len(objs) > 1:
            out.append(
                {
                    "subject": s,
                    "predicate": p,
                    "objects": objs,
                    "triples": rows,
                }
            )
    return out
