#!/usr/bin/env python3
"""
llm-wiki MCP Server — stdio JSON-RPC transport (zero external deps).

Install:
  claude mcp add llm-wiki -- python3 /path/to/wiki-llm/scripts/mcp_server.py [--vault /path/to/vault]

Exposes vault read, write, search, and knowledge-graph tools over MCP.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.config_loader import load_config, save_config, storage_warnings
from lib.paths import resolve_vault, plugin_root
from lib.search import get_search_backend
from lib.knowledge_graph import get_kg_backend
from lib.metrics import get_metrics

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
logger = logging.getLogger("llm_wiki_mcp")

__version__ = "0.2.0"

# ---------------------------------------------------------------------------
# Vault resolution
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="llm-wiki MCP server")
    p.add_argument("--vault", metavar="PATH", help="Override vault path")
    args, _ = p.parse_known_args()
    return args

_args = _parse_args()
_vault = resolve_vault(override=_args.vault)
_cfg = load_config(_vault)
if not (_cfg.get("mcp") or {}).get("enabled", True):
    logger.error("MCP server is disabled (mcp.enabled=false in config.json). Enable it to start.")
    sys.exit(1)
_metrics = get_metrics(_vault, _cfg)
_search = get_search_backend(_vault, _cfg)
_search._metrics = _metrics  # type: ignore[attr-defined]
_kg = get_kg_backend(_vault, _cfg)
_kg._metrics = _metrics  # type: ignore[attr-defined]


def _no_vault() -> dict[str, Any]:
    return {"error": "No vault found", "hint": "Run: llm-wiki setup"}


def _vault_ok() -> bool:
    return (_vault / "config.json").is_file()


# ============================================================================
# READ TOOLS
# ============================================================================

def tool_wiki_wake_up() -> dict[str, Any]:
    """Load L0+L1 context blob for the vault — persona, topics, recent activity."""
    if not _vault_ok():
        return _no_vault()
    from lib.layers import build_wake_up
    return {"context": build_wake_up(_vault, _cfg)}


def tool_wiki_status() -> dict[str, Any]:
    """Vault overview: file counts, config, backend modes, health."""
    if not _vault_ok():
        return _no_vault()
    raw_count = len(list((_vault / "raw").rglob("*.md"))) if (_vault / "raw").exists() else 0
    wiki_count = len(list((_vault / "wiki").rglob("*.md"))) if (_vault / "wiki").exists() else 0
    mcp_cfg = _cfg.get("mcp") or {}
    kg_cfg = _cfg.get("knowledge_graph") or {}
    idx = _search.index_status()
    configured_sb = mcp_cfg.get("search_backend", "fts5")
    active_sb = idx.get("backend", "?")
    fallback = (configured_sb == "chromadb" and active_sb == "grep") or (
        configured_sb == "hybrid" and active_sb == "fts5"
    )
    sw = storage_warnings(_vault, _cfg)
    out: dict[str, Any] = {
        "vault_path": str(_vault),
        "raw_files": raw_count,
        "wiki_pages": wiki_count,
        "persona": (_cfg.get("persona") or {}).get("name", "Gennie"),
        "search_backend": configured_sb,
        "search_backend_active": active_sb,
        "search_backend_fallback": fallback,
        "kg_backend": kg_cfg.get("backend", "json"),
        "git_enabled": (_cfg.get("git") or {}).get("enabled", False),
    }
    if sw:
        out["storage_warnings"] = sw
    return out


def tool_wiki_list_topics() -> dict[str, Any]:
    """Tag index with wiki coverage markers."""
    if not _vault_ok():
        return _no_vault()
    tags_path = _vault / "raw" / ".tags.json"
    if not tags_path.exists():
        return {"topics": [], "hint": "No tag index. Run: llm-wiki ingest ... --tags <topics>"}
    index = json.loads(tags_path.read_text(encoding="utf-8"))
    from lib.layers import _wiki_page_for_tag
    topics = []
    for tag, files in sorted(index.items(), key=lambda kv: -len(kv[1])):
        wp = _wiki_page_for_tag(_vault, tag)
        topics.append({
            "tag": tag,
            "raw_files": len(files),
            "wiki_page": wp,
            "has_wiki": wp is not None,
        })
    return {"topics": topics}


def tool_wiki_validate() -> dict[str, Any]:
    """Vault health check — returns list of issues (empty = healthy)."""
    if not _vault_ok():
        return _no_vault()
    errs: list[str] = []
    for p in [_vault / "config.json", _vault / "wiki" / "index.md", _vault / "CLAUDE.md"]:
        if not p.is_file():
            errs.append(f"missing {p.relative_to(_vault)}")
    return {"valid": len(errs) == 0, "issues": errs}


def tool_wiki_read_page(path: str) -> dict[str, Any]:
    """Read markdown + frontmatter from a wiki/ or raw/ file."""
    if not _vault_ok():
        return _no_vault()
    full = (_vault / path).resolve()
    try:
        full.relative_to(_vault.resolve())
    except ValueError:
        return {"error": "Path escapes vault"}
    if not full.is_file():
        return {"error": f"File not found: {path}"}
    text = full.read_text(encoding="utf-8", errors="replace")
    from lib.search import _parse_frontmatter, _title_from, _tags_for_file
    fm, body = _parse_frontmatter(text)
    return {
        "path": path,
        "title": _title_from(fm, body, path),
        "frontmatter": fm,
        "tags": _tags_for_file(fm),
        "content": text,
    }


def tool_wiki_graph() -> dict[str, Any]:
    """JSON graph of wiki pages: nodes + edges."""
    if not _vault_ok():
        return _no_vault()
    from lib.sitegen import collect_wiki
    raw = collect_wiki(_vault, _cfg)
    nodes = [{"id": n["id"], "title": n.get("title", n["id"]), "path": n.get("path")} for n in raw.get("nodes", [])]
    return {"nodes": nodes, "edges": raw.get("edges", []), "count": len(nodes)}


def tool_wiki_git_status() -> dict[str, Any]:
    """Vault git state."""
    if not _vault_ok():
        return _no_vault()
    if not (_cfg.get("git") or {}).get("enabled"):
        return {"enabled": False, "hint": "Git disabled in config.json"}
    from lib import git as vgit
    try:
        status = vgit.git_status(_vault, _cfg)
        return {"enabled": True, "status": status}
    except vgit.GitDisabledError as e:
        return {"enabled": False, "error": str(e)}


def tool_wiki_search(query: str, limit: int = 5, tag: str = "", scope: str = "all") -> dict[str, Any]:
    """Search vault content. Uses FTS5/BM25 by default."""
    if not _vault_ok():
        return _no_vault()
    results = _search.search(query, limit=limit, tag=tag or None, scope=scope)
    return {"results": [r.to_dict() for r in results], "count": len(results), "backend": _search.index_status().get("backend", "unknown")}


def tool_wiki_find_related(page_path: str, limit: int = 5) -> dict[str, Any]:
    """Find pages semantically similar to a given page."""
    if not _vault_ok():
        return _no_vault()
    results = _search.find_related(page_path, limit=limit)
    return {"results": [r.to_dict() for r in results], "count": len(results)}


def tool_wiki_search_index_status() -> dict[str, Any]:
    """Show search index stats."""
    return _search.index_status()


def tool_wiki_kg_query(entity: str, as_of: str = "") -> dict[str, Any]:
    """Query entity relationships from the knowledge graph."""
    if not (_cfg.get("knowledge_graph") or {}).get("enabled", True):
        return {"disabled": True, "hint": "Knowledge graph disabled in config.json"}
    results = _kg.query_entity(entity, as_of=as_of or None)
    return {"entity": entity, "facts": results, "count": len(results)}


def tool_wiki_kg_timeline(entity: str = "") -> dict[str, Any]:
    """Chronological history of an entity (or all facts)."""
    if not (_cfg.get("knowledge_graph") or {}).get("enabled", True):
        return {"disabled": True}
    results = _kg.timeline(entity or None)
    return {"entity": entity or "all", "timeline": results, "count": len(results)}


def tool_wiki_kg_stats() -> dict[str, Any]:
    """Knowledge graph overview."""
    if not (_cfg.get("knowledge_graph") or {}).get("enabled", True):
        return {"disabled": True}
    return _kg.stats()


# ============================================================================
# WRITE TOOLS
# ============================================================================

def tool_wiki_ingest(adapter: str, source: str, tags: str = "", out: str = "") -> dict[str, Any]:
    """Trigger an ingest adapter (url, file, pdf, etc.)."""
    if not _vault_ok():
        return _no_vault()
    from ingest.registry import adapter_map, run_ingest
    adapters = adapter_map()
    if adapter not in adapters:
        return {"error": f"Unknown adapter: {adapter}", "available": list(adapters.keys())}
    argv = [adapter, source]
    if tags:
        argv.extend(["--tags", tags])
    if out:
        argv.extend(["--out", out])
    try:
        result = run_ingest(_vault, _cfg, adapter, argv[1:])
        return {"success": True, "adapter": adapter, "result": str(result)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_wiki_raw_validate(path: str) -> dict[str, Any]:
    """Validate a raw/ file."""
    if not _vault_ok():
        return _no_vault()
    from lib.raw_markdown import validate_raw_markdown
    rel = path.replace("\\", "/").strip().lstrip("/")
    if rel.startswith("raw/"):
        rel = rel[4:]
    mem_dir = ((_cfg.get("memory") or {}).get("dir") or "raw/memory").replace("\\", "/").strip("/")
    if mem_dir.startswith("raw/"):
        mem_dir = mem_dir[4:]
    if rel == mem_dir or rel.startswith(mem_dir + "/"):
        return {"valid": True, "path": f"raw/{rel}", "skipped": "session memory"}
    full = _vault / "raw" / rel
    if not full.is_file():
        return {"error": f"Not a file: raw/{rel}"}
    text = full.read_text(encoding="utf-8", errors="replace")
    issues = validate_raw_markdown(text)
    return {"valid": len(issues) == 0, "path": f"raw/{rel}", "issues": issues}


def tool_wiki_build_site() -> dict[str, Any]:
    """Rebuild the static viewer."""
    if not _vault_ok():
        return _no_vault()
    from lib.sitegen import build_site
    try:
        out = build_site(_vault, _cfg)
        return {"success": True, "output": str(out)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_wiki_configure(key: str, value: str) -> dict[str, Any]:
    """Update a config.json key (dot-separated path, e.g. 'mcp.search_backend')."""
    if not _vault_ok():
        return _no_vault()
    cfg = load_config(_vault)
    parts = key.split(".")
    target = cfg
    for part in parts[:-1]:
        if part not in target or not isinstance(target[part], dict):
            target[part] = {}
        target = target[part]
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        parsed = value
    target[parts[-1]] = parsed
    save_config(_vault, cfg)
    return {"success": True, "key": key, "value": parsed}


def tool_wiki_reindex() -> dict[str, Any]:
    """Rebuild the search index from vault files."""
    if not _vault_ok():
        return _no_vault()
    return _search.reindex()


def tool_wiki_kg_add(subject: str, predicate: str, object_: str, valid_from: str = "", source: str = "") -> dict[str, Any]:
    """Add a fact triple to the knowledge graph."""
    if not (_cfg.get("knowledge_graph") or {}).get("enabled", True):
        return {"disabled": True}
    tid = _kg.add_triple(subject, predicate, object_, valid_from=valid_from or None, source=source or None)
    return {"success": True, "triple_id": tid, "fact": f"{subject} → {predicate} → {object_}"}


def tool_wiki_kg_invalidate(subject: str, predicate: str, object_: str, ended: str = "") -> dict[str, Any]:
    """Mark a fact as no longer true."""
    if not (_cfg.get("knowledge_graph") or {}).get("enabled", True):
        return {"disabled": True}
    found = _kg.invalidate(subject, predicate, object_, ended=ended or None)
    return {"success": found, "fact": f"{subject} → {predicate} → {object_}", "ended": ended or "today"}


def tool_wiki_kg_rebuild() -> dict[str, Any]:
    """Rebuild knowledge graph from vault files (wikilinks + tags)."""
    if not (_cfg.get("knowledge_graph") or {}).get("enabled", True):
        return {"disabled": True}
    return _kg.rebuild(_vault)


def tool_memory_save(
    session_id: str = "",
    summary: str = "",
    compact_summary: str = "",
    tags: str = "",
    current: bool = False,
    metadata: str = "",
) -> dict[str, Any]:
    """Update session memory markdown. Prefer CLI when local."""
    from lib import session_memory as mem

    if not _vault_ok():
        return _no_vault()
    if not mem.memory_enabled(_cfg):
        return {"skipped": True, "reason": "memory.enabled is false"}
    try:
        sid = mem.resolve_current_session(_vault) if current else session_id.strip()
        if not sid:
            return {"error": "Pass session_id or current=true"}
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    meta = None
    if metadata.strip():
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError:
            return {"error": "metadata must be valid JSON"}
    path = mem.memory_save(
        _vault,
        _cfg,
        sid,
        summary=summary or None,
        compact_summary=compact_summary or None,
        tags=tag_list,
        metadata=meta,
    )
    return {"path": path.relative_to(_vault).as_posix(), "ok": True}


def tool_memory_log(
    session_id: str = "",
    current: bool = False,
    message_preview: str = "",
) -> dict[str, Any]:
    """Append a conversation round to session memory. Prefer CLI when local."""
    from lib import session_memory as mem

    if not _vault_ok():
        return _no_vault()
    if not mem.memory_enabled(_cfg):
        return {"skipped": True, "reason": "memory.enabled is false"}
    try:
        sid = mem.resolve_current_session(_vault) if current else session_id.strip()
        if not sid:
            return {"error": "Pass session_id or current=true"}
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    path = mem.memory_log_round(
        _vault,
        _cfg,
        sid,
        message_preview=message_preview or None,
    )
    return {"path": path.relative_to(_vault).as_posix(), "ok": True}


def tool_memory_list(session_id: str = "", tag: str = "") -> dict[str, Any]:
    """List session memory files."""
    from lib import session_memory as mem

    if not _vault_ok():
        return _no_vault()
    rows = mem.memory_list(_vault, _cfg, session_id=session_id or None, tag=tag or None)
    return {"sessions": rows, "count": len(rows)}


def tool_memory_show(session_id: str = "", current: bool = False) -> dict[str, Any]:
    """Read one session memory file."""
    from lib import session_memory as mem

    if not _vault_ok():
        return _no_vault()
    try:
        sid = mem.resolve_current_session(_vault) if current else session_id.strip()
        if not sid:
            return {"error": "Pass session_id or current=true"}
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    try:
        text = mem.memory_show(_vault, _cfg, sid)
    except FileNotFoundError as e:
        return {"error": str(e)}
    return {"content": text, "session_id": sid}


def tool_memory_recall(
    query: str,
    session_id: str = "",
    tag: str = "",
    limit: int = 5,
    current: bool = False,
) -> dict[str, Any]:
    """Search session memories (scope=memory). Prefer CLI when local."""
    from lib import session_memory as mem

    if not _vault_ok():
        return _no_vault()
    if not query.strip():
        return {"error": "query required"}
    sf = None
    if current:
        try:
            sf = mem.resolve_current_session(_vault)
        except (ValueError, FileNotFoundError) as e:
            return {"error": str(e)}
    elif session_id.strip():
        sf = session_id.strip()
    results = mem.memory_recall(
        _vault,
        _cfg,
        query.strip(),
        session_id=sf,
        tag=tag or None,
        limit=limit,
    )
    return {"results": [r.to_dict() for r in results], "count": len(results)}


def tool_memory_prune(
    session_id: str = "",
    tag: str = "",
    older_than_days: int = 0,
    keep: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete session memory files."""
    from lib import session_memory as mem

    if not _vault_ok():
        return _no_vault()
    if not mem.memory_enabled(_cfg):
        return {"skipped": True, "reason": "memory.enabled is false"}
    try:
        out = mem.memory_prune(
            _vault,
            _cfg,
            session_id=session_id or None,
            tag=tag or None,
            older_than_days=older_than_days if older_than_days > 0 else None,
            keep=keep if keep > 0 else None,
            dry_run=dry_run,
        )
    except ValueError as e:
        return {"error": str(e)}
    return out


def tool_wiki_benchmark_run(
    suite: str = "lme",
    limit: int = 10,
    backend: str = "fts5",
    compressor: str = "raw",
    use_llm: bool = False,
) -> dict[str, Any]:
    """
    Run a retrieval benchmark (LME, LoCoMo, ConvoMem) using the vault's config.
    Set use_llm true to set LLM_WIKI_BENCHMARK_LLM=1 for this run (API or CLI rerank per config).
    """
    if not _vault_ok():
        return _no_vault()
    bcfg = _cfg.get("benchmark") or {}
    if not bcfg.get("enabled", True):
        return {
            "error": "benchmark.enabled is false",
            "hint": "Set benchmark.enabled to true in config.json",
        }
    root = plugin_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    suite_norm = "lme" if suite in ("lme", "longmemeval") else str(suite).lower()
    old_llm = os.environ.get("LLM_WIKI_BENCHMARK_LLM")
    try:
        if use_llm:
            os.environ["LLM_WIKI_BENCHMARK_LLM"] = "1"
        cfg_run = load_config(_vault)
        cfg_run.setdefault("benchmark", {})["auto_record_metrics"] = False
        cfg_run.setdefault("benchmark", {})["compress_method"] = compressor
        be = str(backend).lower()
        lim = int(limit)

        if suite_norm == "lme":
            from benchmarks.lme_bench import download_dataset, finalize_lme_run, run_lme

            cache = Path(
                os.path.expanduser(bcfg.get("data_cache_dir", "~/.cache/llm-wiki-benchmarks"))
            )
            data_path = download_dataset(cache)
            result = run_lme(
                data_path,
                _vault,
                cfg_run,
                backend=be,
                compressor_name=compressor,
                limit=lim,
                top_k=5,
            )
            fail_path = finalize_lme_run(
                _vault,
                cfg_run,
                result,
                backend=be,
                compressor=compressor,
            )
            return {
                "summary": result["summary"],
                "failure_count": len(result["failures"]),
                "failures_log": str(fail_path),
            }
        if suite_norm == "locomo":
            from benchmarks.locomo_bench import run_locomo

            return {"summary": run_locomo(_vault, cfg_run, limit=lim, data_path=None).get("summary", {})}
        if suite_norm == "convomem":
            from benchmarks.convomem_bench import run_convomem

            return {"summary": run_convomem(_vault, cfg_run, limit=lim, data_path=None).get("summary", {})}
        return {"error": f"unknown suite: {suite}", "hint": "use lme | locomo | convomem"}
    finally:
        if old_llm is None:
            os.environ.pop("LLM_WIKI_BENCHMARK_LLM", None)
        else:
            os.environ["LLM_WIKI_BENCHMARK_LLM"] = old_llm


# ============================================================================
# TOOL REGISTRY
# ============================================================================

TOOLS: dict[str, dict[str, Any]] = {
    # -- Read --
    "wiki_wake_up": {
        "description": "Load L0+L1 context blob — persona, topics, recent activity. Call this on session start.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_wake_up,
    },
    "wiki_status": {
        "description": "Vault overview: file counts, config, backend modes.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_status,
    },
    "wiki_list_topics": {
        "description": "Tag index with wiki coverage markers.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_list_topics,
    },
    "wiki_validate": {
        "description": "Vault health check — returns issues (empty = healthy).",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_validate,
    },
    "wiki_read_page": {
        "description": "Read markdown + frontmatter from a wiki/ or raw/ file.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative path within vault, e.g. wiki/auth.md"}},
            "required": ["path"],
        },
        "handler": tool_wiki_read_page,
    },
    "wiki_graph": {
        "description": "JSON graph of wiki pages: nodes and edges (wikilinks + md links).",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_graph,
    },
    "wiki_git_status": {
        "description": "Vault git state (short status).",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_git_status,
    },
    "wiki_search": {
        "description": "Search vault content. FTS5/BM25 by default, ChromaDB if configured. Returns ranked results with snippets.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results (default 5)"},
                "tag": {"type": "string", "description": "Filter by tag (optional)"},
                "scope": {"type": "string", "description": "all | wiki | raw | memory (default: all)"},
            },
            "required": ["query"],
        },
        "handler": tool_wiki_search,
    },
    "wiki_find_related": {
        "description": "Find pages related to a given page (by title/tag similarity).",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_path": {"type": "string", "description": "Path to the page, e.g. wiki/auth.md"},
                "limit": {"type": "integer", "description": "Max results (default 5)"},
            },
            "required": ["page_path"],
        },
        "handler": tool_wiki_find_related,
    },
    "wiki_search_index_status": {
        "description": "Search index stats: backend, file count, last indexed.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_search_index_status,
    },
    "wiki_kg_query": {
        "description": "Query entity relationships from the knowledge graph. Returns current facts for an entity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Entity name to look up"},
                "as_of": {"type": "string", "description": "Point-in-time filter (YYYY-MM-DD, optional)"},
            },
            "required": ["entity"],
        },
        "handler": tool_wiki_kg_query,
    },
    "wiki_kg_timeline": {
        "description": "Chronological history of an entity, or all facts if no entity given.",
        "input_schema": {
            "type": "object",
            "properties": {"entity": {"type": "string", "description": "Entity (optional — omit for full timeline)"}},
        },
        "handler": tool_wiki_kg_timeline,
    },
    "wiki_kg_stats": {
        "description": "Knowledge graph overview: entity count, triple count, predicates.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_kg_stats,
    },
    # -- Write --
    "wiki_ingest": {
        "description": "Trigger an ingest adapter (url, file, pdf, youtube, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "adapter": {"type": "string", "description": "Adapter name (url, file, pdf, youtube, brave, etc.)"},
                "source": {"type": "string", "description": "Source URL or file path"},
                "tags": {"type": "string", "description": "Comma-separated tags (optional)"},
                "out": {"type": "string", "description": "Output path under raw/ (optional)"},
            },
            "required": ["adapter", "source"],
        },
        "handler": tool_wiki_ingest,
    },
    "wiki_raw_validate": {
        "description": "Validate a raw/ file for structural issues.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path under raw/, e.g. notes/auth.md"}},
            "required": ["path"],
        },
        "handler": tool_wiki_raw_validate,
    },
    "wiki_build_site": {
        "description": "Rebuild the static wiki viewer.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_build_site,
    },
    "wiki_configure": {
        "description": "Update a config.json key. Dot-separated path, e.g. 'mcp.search_backend'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Config key path (dot-separated)"},
                "value": {"type": "string", "description": "New value (JSON-parsed if valid, string otherwise)"},
            },
            "required": ["key", "value"],
        },
        "handler": tool_wiki_configure,
    },
    "wiki_reindex": {
        "description": "Rebuild the search index from vault files.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_reindex,
    },
    "wiki_kg_add": {
        "description": "Add a fact triple to the knowledge graph. E.g. ('team', 'decided_to_use', 'GraphQL').",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Entity doing/being something"},
                "predicate": {"type": "string", "description": "Relationship (e.g. 'uses', 'decided_to_use', 'assigned_to')"},
                "object_": {"type": "string", "description": "Connected entity"},
                "valid_from": {"type": "string", "description": "When this became true (YYYY-MM-DD, optional)"},
                "source": {"type": "string", "description": "Source file path (optional)"},
            },
            "required": ["subject", "predicate", "object_"],
        },
        "handler": tool_wiki_kg_add,
    },
    "wiki_kg_invalidate": {
        "description": "Mark a fact as no longer true (set end date).",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Entity"},
                "predicate": {"type": "string", "description": "Relationship"},
                "object_": {"type": "string", "description": "Connected entity"},
                "ended": {"type": "string", "description": "When it stopped being true (YYYY-MM-DD, default: today)"},
            },
            "required": ["subject", "predicate", "object_"],
        },
        "handler": tool_wiki_kg_invalidate,
    },
    "wiki_kg_rebuild": {
        "description": "Rebuild knowledge graph from vault files (extracts wikilinks + tags).",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_kg_rebuild,
    },
    "memory_save": {
        "description": "Update session memory (raw/memory/<id>.md). Prefer: llm-wiki memory save --current …",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Chat session id (omit if current=true)"},
                "current": {"type": "boolean", "description": "Use .current-session in vault"},
                "summary": {"type": "string", "description": "Agent notes section"},
                "compact_summary": {"type": "string", "description": "Compact summary section"},
                "tags": {"type": "string", "description": "Comma-separated tags"},
                "metadata": {"type": "string", "description": "JSON object string (optional)"},
            },
        },
        "handler": tool_memory_save,
    },
    "memory_log": {
        "description": "Append a conversation round to session memory. Prefer: llm-wiki memory log",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Chat session id (omit if current=true)"},
                "current": {"type": "boolean", "description": "Use .current-session in vault"},
                "message_preview": {"type": "string", "description": "Short preview of the conversation round (max 500 chars)"},
            },
        },
        "handler": tool_memory_log,
    },
    "memory_list": {
        "description": "List session memory files. Prefer: llm-wiki memory list",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Filter: id, glob, or comma list"},
                "tag": {"type": "string", "description": "Filter by frontmatter tag"},
            },
        },
        "handler": tool_memory_list,
    },
    "memory_show": {
        "description": "Read one session memory file. Prefer: llm-wiki memory show --current",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "current": {"type": "boolean"},
            },
        },
        "handler": tool_memory_show,
    },
    "memory_recall": {
        "description": "Search session memories (indexed). Prefer: llm-wiki memory recall …",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "session_id": {"type": "string", "description": "Scope to session(s)"},
                "tag": {"type": "string"},
                "limit": {"type": "integer"},
                "current": {"type": "boolean", "description": "Scope to current session"},
            },
            "required": ["query"],
        },
        "handler": tool_memory_recall,
    },
    "memory_prune": {
        "description": "Delete session memory files. Prefer: llm-wiki memory prune …",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "tag": {"type": "string"},
                "older_than_days": {"type": "integer"},
                "keep": {"type": "integer"},
                "dry_run": {"type": "boolean"},
            },
        },
        "handler": tool_memory_prune,
    },
    "wiki_benchmark_run": {
        "description": "Run retrieval benchmark (LME / LoCoMo / ConvoMem) with vault config. CLI: llm-wiki benchmark run …",
        "input_schema": {
            "type": "object",
            "properties": {
                "suite": {
                    "type": "string",
                    "description": "lme | locomo | convomem (aliases: longmemeval → lme)",
                },
                "limit": {"type": "integer", "description": "Max questions (0 = all)"},
                "backend": {"type": "string", "description": "fts5 | grep | chromadb | hybrid"},
                "compressor": {"type": "string", "description": "raw | steno | prune | extract | compact"},
                "use_llm": {
                    "type": "boolean",
                    "description": "Set LLM_WIKI_BENCHMARK_LLM=1 for this run (rerank per benchmark.search.rerank_llm)",
                },
            },
        },
        "handler": tool_wiki_benchmark_run,
    },
}


# ============================================================================
# MCP JSON-RPC PROTOCOL (stdio)
# ============================================================================

def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "llm-wiki", "version": __version__},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        tool_list = [
            {"name": name, "description": t["description"], "inputSchema": t["input_schema"]}
            for name, t in TOOLS.items()
        ]
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tool_list}}

    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        if tool_name not in TOOLS:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }
        schema_props = TOOLS[tool_name]["input_schema"].get("properties", {})
        for key, value in list(tool_args.items()):
            declared = schema_props.get(key, {}).get("type")
            if declared == "integer" and not isinstance(value, int):
                try:
                    tool_args[key] = int(value)
                except (ValueError, TypeError):
                    pass
        import time as _time
        _t0 = _time.monotonic()
        try:
            result = TOOLS[tool_name]["handler"](**tool_args)
            _elapsed = round((_time.monotonic() - _t0) * 1000, 1)
            _metrics.record("mcp.tool_call", _elapsed, meta={"tool": tool_name}, tags=["mcp"])
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]},
            }
        except Exception as e:
            logger.exception(f"Tool error in {tool_name}")
            _metrics.record("mcp.tool_error", 1, meta={"tool": tool_name, "error": str(e)[:200]}, tags=["mcp", "error"])
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32000, "message": f"Tool error: {e}"},
            }

    return {
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


def main() -> None:
    logger.info("llm-wiki MCP server starting (vault: %s)...", _vault)
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except KeyboardInterrupt:
            break
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON: %s", e)
        except Exception as e:
            logger.error("Server error: %s", e)


if __name__ == "__main__":
    main()
