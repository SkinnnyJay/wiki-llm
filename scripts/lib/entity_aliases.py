"""Canonicalize entity names via knowledge_graph.aliases."""

from __future__ import annotations

from typing import Any


def alias_lookup_table(cfg: dict[str, Any] | None) -> dict[str, str]:
    """
    Build case-insensitive alias → canonical map.

    Config shape::
        "knowledge_graph": {
          "aliases": {"OAuth2": "OAuth", "AuthN": "Authentication"}
        }
    """
    kg = (cfg or {}).get("knowledge_graph") or {}
    raw = kg.get("aliases") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for alias, canonical in raw.items():
        a = str(alias).strip()
        c = str(canonical).strip()
        if not a or not c:
            continue
        out[a.casefold()] = c
        # Also allow looking up the canonical itself
        out[c.casefold()] = c
    return out


def canonicalize_entity(name: str, cfg: dict[str, Any] | None = None) -> str:
    """Return canonical entity label (unchanged if no alias match)."""
    s = (name or "").strip()
    if not s:
        return s
    table = alias_lookup_table(cfg)
    if not table:
        return s
    return table.get(s.casefold(), s)


def canonicalize_triple(
    subject: str,
    predicate: str,
    object_: str,
    cfg: dict[str, Any] | None = None,
) -> tuple[str, str, str]:
    return (
        canonicalize_entity(subject, cfg),
        (predicate or "").strip(),
        canonicalize_entity(object_, cfg),
    )
