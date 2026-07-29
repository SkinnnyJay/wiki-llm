"""Light predicate ontology for knowledge_graph.allowed_predicates."""

from __future__ import annotations

from typing import Any

from lib.fact_checker import MULTI_VALUED_PREDICATES

# Always permitted structural / common edges from rebuild + docs.
BUILTIN_ALLOWED = frozenset(MULTI_VALUED_PREDICATES) | frozenset(
    {
        "is_a",
        "uses",
        "part_of",
        "depends_on",
        "implements",
        "conflicts_with",
        "same_as",
        "see_also",
    }
)


def allowed_predicates(cfg: dict[str, Any] | None) -> frozenset[str] | None:
    """
    Return the allowlist, or None when unrestricted.

    Empty list / missing key → unrestricted (backward compatible).
    Non-empty list → only those predicates (+ builtins unless
    knowledge_graph.ontology_strict is true).
    """
    kg = (cfg or {}).get("knowledge_graph") or {}
    raw = kg.get("allowed_predicates")
    if raw is None:
        return None
    if not isinstance(raw, list):
        return None
    cleaned = {str(p).strip() for p in raw if str(p).strip()}
    if not cleaned:
        return None
    if kg.get("ontology_strict"):
        return frozenset(cleaned)
    return frozenset(cleaned) | BUILTIN_ALLOWED


def predicate_allowed(predicate: str, cfg: dict[str, Any] | None = None) -> bool:
    allow = allowed_predicates(cfg)
    if allow is None:
        return True
    return (predicate or "").strip() in allow


def ontology_error(predicate: str, cfg: dict[str, Any] | None = None) -> str | None:
    if predicate_allowed(predicate, cfg):
        return None
    allow = allowed_predicates(cfg) or frozenset()
    sample = ", ".join(sorted(allow)[:12])
    return (
        f"Predicate {predicate!r} not in knowledge_graph.allowed_predicates "
        f"(examples: {sample}{'…' if len(allow) > 12 else ''})"
    )
