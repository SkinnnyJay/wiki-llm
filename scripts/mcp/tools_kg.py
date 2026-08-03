"""MCP knowledge-graph tool handlers."""
from __future__ import annotations

from typing import Any

from mcp.ctx import (
    get_cfg,
    get_kg,
    require_vault,
)


def tool_wiki_kg_query(entity: str, as_of: str = "") -> dict[str, Any]:
    """Query entity relationships from the knowledge graph."""
    if not (get_cfg().get("knowledge_graph") or {}).get("enabled", True):
        return {"disabled": True, "hint": "Knowledge graph disabled in config.json"}
    results = get_kg().query_entity(entity, as_of=as_of or None)
    return {"entity": entity, "facts": results, "count": len(results)}

def tool_wiki_kg_timeline(entity: str = "") -> dict[str, Any]:
    """Chronological history of an entity (or all facts)."""
    if not (get_cfg().get("knowledge_graph") or {}).get("enabled", True):
        return {"disabled": True}
    results = get_kg().timeline(entity or None)
    return {"entity": entity or "all", "timeline": results, "count": len(results)}

def tool_wiki_kg_stats() -> dict[str, Any]:
    """Knowledge graph overview."""
    if not (get_cfg().get("knowledge_graph") or {}).get("enabled", True):
        return {"disabled": True}
    return get_kg().stats()

def tool_wiki_kg_traverse(start: str, max_depth: int = 2) -> dict[str, Any]:
    """BFS over KG triples from an entity (undirected)."""
    if not (get_cfg().get("knowledge_graph") or {}).get("enabled", True):
        return {"disabled": True}
    if not hasattr(get_kg(), "traverse_bfs"):
        return {"error": "KG backend has no traverse_bfs"}
    trips = get_kg().traverse_bfs(start, max_depth=max_depth)
    return {"start": start, "max_depth": max_depth, "triples": trips, "count": len(trips)}

def tool_wiki_find_connections(
    entity_a: str, entity_b: str, max_depth: int = 12
) -> dict[str, Any]:
    """Shortest triple-path between two entities (if any)."""
    if not (get_cfg().get("knowledge_graph") or {}).get("enabled", True):
        return {"disabled": True}
    if not hasattr(get_kg(), "find_connection_path"):
        return {"error": "KG backend has no find_connection_path"}
    path = get_kg().find_connection_path(entity_a, entity_b, max_depth=max_depth)
    return {
        "entity_a": entity_a,
        "entity_b": entity_b,
        "path_triples": path,
        "found": path is not None,
    }

def tool_wiki_kg_add(subject: str, predicate: str, object_: str, valid_from: str = "", source: str = "") -> dict[str, Any]:
    """Add a fact triple to the knowledge graph."""
    if not (get_cfg().get("knowledge_graph") or {}).get("enabled", True):
        return {"disabled": True}
    cfg = get_cfg()
    kg_cfg = cfg.get("knowledge_graph") or {}
    if kg_cfg.get("fact_check_on_add", True):
        from lib.fact_checker import conflicting_objects_for_predicate

        conflicts = conflicting_objects_for_predicate(
            get_kg(), subject, predicate, object_, cfg=cfg
        )
        if conflicts:
            return {
                "success": False,
                "conflicts": conflicts,
                "hint": "Existing triple(s) with same subject+predicate but different object; invalidate or adjust.",
            }
    try:
        tid = get_kg().add_triple(
            subject, predicate, object_, valid_from=valid_from or None, source=source or None
        )
    except ValueError as exc:
        return {"success": False, "error": str(exc)}
    return {"success": True, "triple_id": tid, "fact": f"{subject} → {predicate} → {object_}"}

def tool_wiki_kg_invalidate(subject: str, predicate: str, object_: str, ended: str = "") -> dict[str, Any]:
    """Mark a fact as no longer true."""
    if not (get_cfg().get("knowledge_graph") or {}).get("enabled", True):
        return {"disabled": True}
    found = get_kg().invalidate(subject, predicate, object_, ended=ended or None)
    return {"success": found, "fact": f"{subject} → {predicate} → {object_}", "ended": ended or "today"}

def tool_wiki_kg_rebuild() -> dict[str, Any]:
    """Rebuild knowledge graph from vault files (wikilinks + tags)."""
    vault = require_vault()
    from lib.knowledge_graph import rebuild_knowledge_graph

    return rebuild_knowledge_graph(vault, get_cfg(), backend=get_kg())

