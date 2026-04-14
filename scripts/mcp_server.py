#!/usr/bin/env python3
"""
llm-wiki MCP Server — stdio JSON-RPC transport (zero external deps).

Install:
  claude mcp add llm-wiki -- python3 /path/to/wiki-llm/scripts/mcp_server.py [--vault /path/to/vault]

Exposes vault read, write, search, and knowledge-graph tools over MCP.
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.config_loader import load_config, save_config, storage_warnings
from lib.mcp_cli import MCP_DISABLED_MESSAGE, mcp_enabled
from lib.paths import resolve_vault, plugin_root
from lib.search import get_search_backend
from lib.knowledge_graph import get_kg_backend
from lib.metrics import get_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [llm-wiki-mcp] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("llm_wiki_mcp")

__version__ = "0.2.0"

# Reject absurdly large JSON-RPC lines (DoS / accidental paste) — stdio transport.
_MAX_JSON_RPC_LINE_BYTES = 32 * 1024 * 1024


def _mcp_log_extra(
    *,
    request_id: Any = None,
    method: str | None = None,
    tool: str | None = None,
    cancelled_request_id: Any = None,
) -> dict[str, Any]:
    """Keyword fields merged into LogRecord (for aggregators); keys avoid LogRecord builtins."""
    d: dict[str, Any] = {}
    if request_id is not None:
        d["mcp_request_id"] = request_id
    if method:
        d["mcp_method"] = method
    if tool:
        d["mcp_tool"] = tool
    if cancelled_request_id is not None:
        d["mcp_cancelled_request_id"] = cancelled_request_id
    return d


def _mcp_log_line(msg: str, **fields: Any) -> str:
    """Human-readable suffix with key=value pairs for stderr (works without custom formatters)."""
    tail = " ".join(f"{k}={v!r}" for k, v in fields.items() if v is not None)
    return f"{msg} | {tail}" if tail else msg

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
if not mcp_enabled(_cfg):
    logger.error(MCP_DISABLED_MESSAGE)
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


def _mcp_cfg() -> dict[str, Any]:
    return _cfg.get("mcp") or {}


# Cache for tool_wiki_status markdown file counts (mtime + TTL)
_vault_md_count_cache: dict[str, Any] = {"t": 0.0, "raw_sig": None, "wiki_sig": None, "raw_n": 0, "wiki_n": 0}


def _dir_sig(d: Path) -> tuple[int, int]:
    if not d.is_dir():
        return (0, 0)
    st = d.stat()
    return (int(st.st_mtime_ns), int(st.st_size))


def _cached_md_counts() -> tuple[int, int]:
    """Return (raw_md_count, wiki_md_count) using mtime+TTL cache."""
    ttl = float(_mcp_cfg().get("status_file_count_ttl_seconds") or 45)
    raw_dir = _vault / "raw"
    wiki_dir = _vault / "wiki"
    rs, ws = _dir_sig(raw_dir), _dir_sig(wiki_dir)
    now = time.monotonic()
    c = _vault_md_count_cache
    if (
        c.get("raw_sig") == rs
        and c.get("wiki_sig") == ws
        and now - float(c.get("t", 0)) < ttl
    ):
        return (int(c["raw_n"]), int(c["wiki_n"]))
    raw_n = len(list(raw_dir.rglob("*.md"))) if raw_dir.exists() else 0
    wiki_n = len(list(wiki_dir.rglob("*.md"))) if wiki_dir.exists() else 0
    c.update(
        {
            "t": now,
            "raw_sig": rs,
            "wiki_sig": ws,
            "raw_n": raw_n,
            "wiki_n": wiki_n,
        }
    )
    return raw_n, wiki_n


def _configure_key_allowed(key: str, rules: list[Any]) -> bool:
    if not rules:
        return True
    for r in rules:
        if not isinstance(r, str):
            continue
        r = r.strip()
        if not r:
            continue
        if r.endswith("."):
            if key.startswith(r) or key == r[:-1]:
                return True
        elif key == r:
            return True
    return False


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
    raw_count, wiki_count = _cached_md_counts()
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


def tool_wiki_read_page(path: str, max_chars: int = 0) -> dict[str, Any]:
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
    if max_chars is not None and max_chars != 0:
        lim = int(max_chars)
    else:
        lim = int(_mcp_cfg().get("read_page_max_chars") or 0)
    content = text
    truncated = False
    if lim > 0 and len(content) > lim:
        content = content[:lim] + "\n\n[truncated]"
        truncated = True
    return {
        "path": path,
        "title": _title_from(fm, body, path),
        "frontmatter": fm,
        "tags": _tags_for_file(fm),
        "content": content,
        "truncated": truncated,
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


def tool_wiki_search(
    query: str,
    limit: int = 5,
    tag: str = "",
    scope: str = "all",
    wing: str = "",
    room: str = "",
) -> dict[str, Any]:
    """Search vault content. Uses FTS5/BM25 by default."""
    if not _vault_ok():
        return _no_vault()
    results = _search.search(
        query,
        limit=limit,
        tag=tag or None,
        scope=scope,
        wing=wing or None,
        room=room or None,
    )
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


def tool_wiki_check_duplicate(content: str = "", path: str = "") -> dict[str, Any]:
    """Return paths with same content hash as the given body or file (ingest dedup index)."""
    if not _vault_ok():
        return _no_vault()
    from ingest.dedup import check_duplicate, content_hash, strip_llm_wiki_keys

    if path:
        p = (_vault / path).resolve()
        if not p.is_file():
            return {"error": f"not a file: {path}"}
        text = p.read_text(encoding="utf-8", errors="replace")
        h = content_hash(strip_llm_wiki_keys(text))
    elif content:
        h = content_hash(content)
    else:
        return {"error": "provide content or path"}
    dupes = check_duplicate(_vault, h)
    rels: list[str] = []
    for x in dupes:
        try:
            rels.append(str(x.relative_to(_vault)))
        except ValueError:
            rels.append(str(x))
    return {"content_hash": h, "duplicates": rels, "count": len(rels)}


def tool_wiki_kg_traverse(start: str, max_depth: int = 2) -> dict[str, Any]:
    """BFS over KG triples from an entity (undirected)."""
    if not (_cfg.get("knowledge_graph") or {}).get("enabled", True):
        return {"disabled": True}
    if not hasattr(_kg, "traverse_bfs"):
        return {"error": "KG backend has no traverse_bfs"}
    trips = _kg.traverse_bfs(start, max_depth=max_depth)
    return {"start": start, "max_depth": max_depth, "triples": trips, "count": len(trips)}


def tool_wiki_find_connections(
    entity_a: str, entity_b: str, max_depth: int = 12
) -> dict[str, Any]:
    """Shortest triple-path between two entities (if any)."""
    if not (_cfg.get("knowledge_graph") or {}).get("enabled", True):
        return {"disabled": True}
    if not hasattr(_kg, "find_connection_path"):
        return {"error": "KG backend has no find_connection_path"}
    path = _kg.find_connection_path(entity_a, entity_b, max_depth=max_depth)
    return {
        "entity_a": entity_a,
        "entity_b": entity_b,
        "path_triples": path,
        "found": path is not None,
    }


def tool_wiki_agent_diary_read(agent_id: str, max_chars: int = 8000) -> dict[str, Any]:
    """Read per-agent diary under raw/agents/<id>/diary.md."""
    if not _vault_ok():
        return _no_vault()
    from lib.agent_diary import read_diary

    text = read_diary(_vault, agent_id, max_chars=max_chars or 0)
    return {"agent_id": agent_id, "text": text, "chars": len(text)}


def tool_wiki_agent_diary_append(
    agent_id: str, line: str, source: str = ""
) -> dict[str, Any]:
    """Append one markdown bullet line to an agent diary."""
    if not _vault_ok():
        return _no_vault()
    from lib.agent_diary import append_diary

    p = append_diary(_vault, agent_id, line, source=source or None)
    return {"agent_id": agent_id, "path": str(p.relative_to(_vault)), "ok": True}


# ============================================================================
# WRITE TOOLS
# ============================================================================

def tool_wiki_ingest(
    adapter: str,
    source: str,
    tags: str = "",
    out: str = "",
    force: bool = False,
    force_security: bool = False,
) -> dict[str, Any]:
    """Trigger an ingest adapter and run the post-ingest pipeline (matches CLI ingest)."""
    if not _vault_ok():
        return _no_vault()
    if not bool(_mcp_cfg().get("ingest_enabled", True)):
        return {"skipped": True, "reason": "mcp.ingest_enabled is false"}
    from ingest.registry import adapter_map, run_ingest
    from lib.ingest_finish import post_ingest

    adapters = adapter_map()
    if adapter not in adapters:
        return {"error": f"Unknown adapter: {adapter}", "available": list(adapters.keys())}
    argv = [source]
    if out:
        argv.extend(["--out", out])
    try:
        result = run_ingest(_vault, _cfg, adapter, argv, force_adapter=force)
    except SystemExit as e:
        msg = str(e) if str(e) else (str(e.code) if isinstance(e.code, int) else "ingest failed")
        return {"success": False, "error": msg}
    except Exception as e:
        return {"success": False, "error": str(e)}
    manual_tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    try:
        exit_code = post_ingest(
            _vault,
            _cfg,
            result.output_path,
            force=force,
            force_security=force_security,
            commit_body=result.commit_body,
            manual_tags=manual_tags,
        )
    except Exception as e:
        return {"success": False, "adapter": adapter, "ingest_message": result.message, "error": str(e)}
    return {
        "success": exit_code == 0,
        "adapter": adapter,
        "result": result.message,
        "post_ingest_exit_code": exit_code,
    }


def tool_wiki_raw_validate(path: str, autofix: bool = False) -> dict[str, Any]:
    """Validate a raw/ file (optional deterministic autofix, same as CLI)."""
    if not _vault_ok():
        return _no_vault()
    from lib.raw_validate import validate_raw_file_result

    r = validate_raw_file_result(_vault, _cfg, path, autofix=autofix)
    if r.get("error"):
        return {"error": r["error"]}
    out: dict[str, Any] = {
        "valid": r["valid"],
        "path": r["path"],
        "issues": r.get("issues") or [],
    }
    if r.get("skipped"):
        out["skipped"] = r["skipped"]
    if r.get("autofix_applied"):
        out["autofix_applied"] = r["autofix_applied"]
    return out


def tool_wiki_build_site(if_stale: bool = False) -> dict[str, Any]:
    """Rebuild the static viewer. if_stale=true skips build when site is already current."""
    if not _vault_ok():
        return _no_vault()
    from lib.sitegen import build_site, site_is_stale

    if if_stale and not site_is_stale(_vault):
        return {"success": True, "skipped": True, "reason": "site up-to-date"}
    try:
        out = build_site(_vault, _cfg)
        return {"success": True, "output": str(out)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _metrics_recorder_for_read() -> Any:
    cfg = copy.deepcopy(_cfg)
    cfg.setdefault("metrics", {})["enabled"] = True
    from lib.metrics import MetricsRecorder

    return MetricsRecorder(_vault, cfg)


def tool_wiki_metrics_stats() -> dict[str, Any]:
    """Operational metrics summary (same data as `llm-wiki metrics stats`)."""
    if not _vault_ok():
        return _no_vault()
    m = _metrics_recorder_for_read()
    return {"stats": m.stats()}


def tool_wiki_metrics_query(key: str = "", since: str = "", limit: int = 100) -> dict[str, Any]:
    """Query metrics records (read-only; use CLI for record/clear/report)."""
    if not _vault_ok():
        return _no_vault()
    m = _metrics_recorder_for_read()
    records = m.query(key=key or None, since=since or None, limit=int(limit))
    return {"records": records, "count": len(records)}


def tool_wiki_benchmark_suites() -> dict[str, Any]:
    """Describe benchmark suites (same text as `llm-wiki benchmark suites`)."""
    if not _vault_ok():
        return _no_vault()
    root = plugin_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from benchmarks.suite_help import describe_benchmark_suites

    return {"text": describe_benchmark_suites()}


def _safe_benchmark_data_path(data_arg: str | None) -> Path | None:
    """Resolve optional dataset path; must stay under vault or benchmark cache dir."""
    if not (data_arg or "").strip():
        return None
    p = Path(os.path.expanduser(str(data_arg).strip())).resolve()
    bcfg = _cfg.get("benchmark") or {}
    vault_r = _vault.resolve()
    cache = Path(os.path.expanduser(bcfg.get("data_cache_dir", "~/.cache/llm-wiki-benchmarks"))).resolve()
    for root in (vault_r, cache):
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue
    raise ValueError(
        f"data_path must be under vault ({vault_r}) or benchmark cache ({cache}); got {p}"
    )


def tool_wiki_graph_build(mode: str = "links", out: str = "") -> dict[str, Any]:
    """Build D3 graph bundle (HTML/JS) — distinct from wiki_graph JSON."""
    if not _vault_ok():
        return _no_vault()
    from lib.graphgen import build_graph_bundle

    out_dir = Path(out).resolve() if (out or "").strip() else (Path.cwd() / ".tmp" / "llm-wiki-graph").resolve()
    m = str(mode).lower().strip()
    if m not in ("links", "knowledge"):
        return {"success": False, "error": 'mode must be "links" or "knowledge"'}
    try:
        path = build_graph_bundle(_vault, _cfg, out_dir, m)
        return {
            "success": True,
            "output_dir": str(path),
            "hint": f"cd {path} && python3 -m http.server 8890",
        }
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_wiki_configure(key: str, value: str) -> dict[str, Any]:
    """Update a config.json key (dot-separated path, e.g. 'mcp.search_backend')."""
    if not _vault_ok():
        return _no_vault()
    rules = _mcp_cfg().get("configure_allowlist") or []
    if isinstance(rules, list) and rules and not _configure_key_allowed(key, rules):
        return {"success": False, "error": "Key not allowed by mcp.configure_allowlist", "key": key}
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
    kg_cfg = _cfg.get("knowledge_graph") or {}
    if kg_cfg.get("fact_check_on_add", True):
        from lib.fact_checker import conflicting_objects_for_predicate

        conflicts = conflicting_objects_for_predicate(_kg, subject, predicate, object_)
        if conflicts:
            return {
                "success": False,
                "conflicts": conflicts,
                "hint": "Existing triple(s) with same subject+predicate but different object; invalidate or adjust.",
            }
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
    top_k: int = 5,
    data_path: str = "",
    no_metrics: bool = False,
    peers: list[str] | None = None,
    strict_peers: bool = False,
) -> dict[str, Any]:
    """
    Run a retrieval benchmark (LME, LoCoMo, ConvoMem) using the vault's config.
    Set use_llm true to set LLM_WIKI_BENCHMARK_LLM=1 for this run (API or CLI rerank per config).
    data_path: optional dataset file/dir; must be under the vault or benchmark cache (see CLI --data).
    """
    if not _vault_ok():
        return _no_vault()
    bcfg = _cfg.get("benchmark") or {}
    if not bcfg.get("enabled", True):
        return {
            "error": "benchmark.enabled is false",
            "hint": "Set benchmark.enabled to true in config.json",
        }
    try:
        data_resolved = _safe_benchmark_data_path(data_path)
    except ValueError as e:
        return {"error": str(e)}
    root = plugin_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    suite_norm = "lme" if suite in ("lme", "longmemeval") else str(suite).lower()
    old_llm = os.environ.get("LLM_WIKI_BENCHMARK_LLM")
    try:
        if use_llm:
            os.environ["LLM_WIKI_BENCHMARK_LLM"] = "1"
        cfg_run = load_config(_vault)
        cfg_run.setdefault("benchmark", {})["auto_record_metrics"] = not bool(no_metrics)
        cfg_run.setdefault("benchmark", {})["compress_method"] = compressor
        be = str(backend).lower()
        lim = int(limit)
        tk = int(top_k) if int(top_k) > 0 else 5

        if suite_norm == "lme":
            from benchmarks.lme_bench import download_dataset, finalize_lme_run, run_lme

            cache = Path(os.path.expanduser(bcfg.get("data_cache_dir", "~/.cache/llm-wiki-benchmarks")))
            if data_resolved is None:
                lme_data = download_dataset(cache)
            else:
                lme_data = data_resolved
            peer_ids = [str(x) for x in (peers or []) if str(x).strip()]
            if peer_ids:
                from benchmarks.peer_lme import run_lme_peers

                sp = bool(strict_peers) or bool((bcfg.get("peers") or {}).get("strict", False))
                try:
                    out = run_lme_peers(
                        lme_data,
                        _vault,
                        cfg_run,
                        peer_ids=peer_ids,
                        limit=lim,
                        top_k=tk,
                        strict_peers=sp,
                    )
                except RuntimeError as e:
                    return {"error": str(e)}
                return out
            result = run_lme(
                lme_data,
                _vault,
                cfg_run,
                backend=be,
                compressor_name=compressor,
                limit=lim,
                top_k=tk,
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

            return {
                "summary": run_locomo(_vault, cfg_run, limit=lim, data_path=data_resolved).get("summary", {})
            }
        if suite_norm == "convomem":
            from benchmarks.convomem_bench import run_convomem

            return {
                "summary": run_convomem(_vault, cfg_run, limit=lim, data_path=data_resolved).get("summary", {})
            }
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
            "properties": {
                "path": {"type": "string", "description": "Relative path within vault, e.g. wiki/auth.md"},
                "max_chars": {
                    "type": "integer",
                    "description": "Truncate body (0 = use mcp.read_page_max_chars; both 0 = full file)",
                },
            },
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
                "wing": {
                    "type": "string",
                    "description": "Optional palace-style scope: project/person (frontmatter wing / llm_wiki_wing)",
                },
                "room": {
                    "type": "string",
                    "description": "Optional topic scope (frontmatter room / llm_wiki_room)",
                },
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
    "wiki_check_duplicate": {
        "description": "Content-hash duplicate check (same as ingest dedup). Pass raw markdown body or vault-relative path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Raw markdown to hash (optional if path set)"},
                "path": {"type": "string", "description": "Vault-relative path to a file to hash"},
            },
        },
        "handler": tool_wiki_check_duplicate,
    },
    "wiki_kg_traverse": {
        "description": "BFS from an entity over active KG triples (undirected).",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Starting entity name"},
                "max_depth": {"type": "integer", "description": "Hop depth (default 2)"},
            },
            "required": ["start"],
        },
        "handler": tool_wiki_kg_traverse,
    },
    "wiki_find_connections": {
        "description": "Shortest triple-path between two entities (tunnel / bridge discovery).",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_a": {"type": "string"},
                "entity_b": {"type": "string"},
                "max_depth": {"type": "integer", "description": "Max triples on path (default 12)"},
            },
            "required": ["entity_a", "entity_b"],
        },
        "handler": tool_wiki_find_connections,
    },
    "wiki_agent_diary_read": {
        "description": "Read per-agent diary (raw/agents/<id>/diary.md).",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "max_chars": {"type": "integer", "description": "Truncate (0 = full)"},
            },
            "required": ["agent_id"],
        },
        "handler": tool_wiki_agent_diary_read,
    },
    "wiki_agent_diary_append": {
        "description": "Append a line to an agent diary (creates file if missing).",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "line": {"type": "string", "description": "One log line (markdown bullet added)"},
                "source": {"type": "string", "description": "Optional provenance label"},
            },
            "required": ["agent_id", "line"],
        },
        "handler": tool_wiki_agent_diary_append,
    },
    # -- Write --
    "wiki_ingest": {
        "description": "Trigger an ingest adapter (url, file, pdf, youtube, etc.) and run post-ingest pipeline (CLI parity).",
        "input_schema": {
            "type": "object",
            "properties": {
                "adapter": {"type": "string", "description": "Adapter name (url, file, pdf, youtube, brave, etc.)"},
                "source": {"type": "string", "description": "Source URL or file path"},
                "tags": {"type": "string", "description": "Comma-separated tags (optional)"},
                "out": {"type": "string", "description": "Output path under raw/ (optional)"},
                "force": {
                    "type": "boolean",
                    "description": "Bypass integration enable check and dedup/security gates where applicable (matches CLI --force)",
                },
                "force_security": {
                    "type": "boolean",
                    "description": "Run security scan even when ingest security is disabled (CLI --force-security)",
                },
            },
            "required": ["adapter", "source"],
        },
        "handler": tool_wiki_ingest,
    },
    "wiki_raw_validate": {
        "description": "Validate a raw/ file for structural issues (optional autofix, same rules as CLI raw validate).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path under raw/, e.g. notes/auth.md"},
                "autofix": {"type": "boolean", "description": "Apply safe deterministic fixes before validating"},
            },
            "required": ["path"],
        },
        "handler": tool_wiki_raw_validate,
    },
    "wiki_build_site": {
        "description": "Rebuild the static wiki viewer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "if_stale": {
                    "type": "boolean",
                    "description": "If true, skip build when viewer output is already up to date (CLI --if-stale)",
                }
            },
        },
        "handler": tool_wiki_build_site,
    },
    "wiki_metrics_stats": {
        "description": "Metrics file summary (read-only). CLI: llm-wiki metrics stats",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_metrics_stats,
    },
    "wiki_metrics_query": {
        "description": "Query metrics JSONL records (read-only). CLI: llm-wiki metrics query",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Filter by metric key (optional)"},
                "since": {"type": "string", "description": "ISO timestamp lower bound (optional)"},
                "limit": {"type": "integer", "description": "Max records (default 100)"},
            },
        },
        "handler": tool_wiki_metrics_query,
    },
    "wiki_benchmark_suites": {
        "description": "Print benchmark suite help text. CLI: llm-wiki benchmark suites",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_benchmark_suites,
    },
    "wiki_graph_build": {
        "description": "Build D3 link/knowledge graph bundle (HTML) under output dir. Distinct from wiki_graph JSON export.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "description": "links | knowledge"},
                "out": {"type": "string", "description": "Output directory (default: .tmp/llm-wiki-graph under cwd)"},
            },
        },
        "handler": tool_wiki_graph_build,
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
                "top_k": {"type": "integer", "description": "Retrieval depth for LME (default 5)"},
                "data_path": {
                    "type": "string",
                    "description": "Optional dataset path (must be under vault or benchmark cache dir)",
                },
                "no_metrics": {
                    "type": "boolean",
                    "description": "If true, disable auto_record_metrics for this run (CLI --no-metrics)",
                },
                "peers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional peer ids (mem0, mempalace, claude-mem, supermemory) for LME; same LongMemEval JSON as vault LME",
                },
                "strict_peers": {
                    "type": "boolean",
                    "description": "Fail if any peer cannot run (CLI --strict-peers / benchmark.peers.strict)",
                },
            },
        },
        "handler": tool_wiki_benchmark_run,
    },
}

READ_ONLY_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "wiki_wake_up",
        "wiki_status",
        "wiki_list_topics",
        "wiki_validate",
        "wiki_read_page",
        "wiki_graph",
        "wiki_git_status",
        "wiki_search",
        "wiki_find_related",
        "wiki_search_index_status",
        "wiki_kg_query",
        "wiki_kg_timeline",
        "wiki_kg_stats",
        "wiki_check_duplicate",
        "wiki_kg_traverse",
        "wiki_find_connections",
        "wiki_agent_diary_read",
        "wiki_raw_validate",
        "wiki_metrics_stats",
        "wiki_metrics_query",
        "wiki_benchmark_suites",
        "memory_list",
        "memory_show",
        "memory_recall",
    }
)


def build_active_tools(
    cfg: dict[str, Any], registry: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Filter MCP tools per mcp.tools_mode, allowlist, benchmark, and ingest flags."""
    mcp = cfg.get("mcp") or {}
    out = {k: v for k, v in registry.items()}
    if not bool(mcp.get("benchmark_tool_enabled", True)):
        out.pop("wiki_benchmark_run", None)
        out.pop("wiki_benchmark_suites", None)
    if not bool(mcp.get("ingest_enabled", True)):
        out.pop("wiki_ingest", None)
    mode = (mcp.get("tools_mode") or "full").strip().lower()
    allow = mcp.get("tools_allowlist") or []
    if not isinstance(allow, list):
        allow = []
    if mode == "full":
        return out
    if mode == "read_only":
        return {k: v for k, v in out.items() if k in READ_ONLY_TOOL_NAMES}
    if mode == "custom":
        if not allow:
            return {k: v for k, v in out.items() if k in READ_ONLY_TOOL_NAMES}
        allowed_set = {str(x) for x in allow}
        return {k: v for k, v in out.items() if k in allowed_set}
    return out


def get_active_tools() -> dict[str, dict[str, Any]]:
    return build_active_tools(_cfg, TOOLS)


def _sanitize_tool_error_message(_exc: BaseException) -> str:
    return "Tool error — see server logs for details."


def _prepare_tool_arguments(
    tool_name: str, raw_args: dict[str, Any], schema: dict[str, Any]
) -> tuple[dict[str, Any], str | None]:
    """
    Filter to declared properties, coerce integers, validate required.
    Returns (args, error_message).
    """
    props = schema.get("properties") or {}
    filtered: dict[str, Any] = {}
    for k, v in raw_args.items():
        if k not in props:
            continue
        filtered[k] = v
    for key, value in list(filtered.items()):
        declared = props.get(key, {}).get("type")
        if declared == "boolean":
            if isinstance(value, bool):
                continue
            if isinstance(value, str):
                v = value.strip().lower()
                if v in ("true", "1", "yes"):
                    filtered[key] = True
                elif v in ("false", "0", "no"):
                    filtered[key] = False
                else:
                    return filtered, f"Invalid boolean for {key}: {value!r}"
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                filtered[key] = bool(value)
            else:
                return filtered, f"Invalid boolean for {key}: {value!r}"
        elif declared == "integer" and not isinstance(value, bool) and not isinstance(value, int):
            try:
                filtered[key] = int(value)
            except (ValueError, TypeError):
                return filtered, f"Invalid integer for {key}: {value!r}"
    for req in schema.get("required") or []:
        if req not in filtered:
            return filtered, f"Missing required argument: {req}"
    if tool_name == "wiki_search":
        scope = str(filtered.get("scope", "all")).lower()
        if scope not in ("all", "wiki", "raw", "memory"):
            return filtered, f"Invalid scope: {scope!r} (use all|wiki|raw|memory)"
    if tool_name == "wiki_benchmark_run":
        suite = str(filtered.get("suite", "lme")).lower()
        if suite not in ("lme", "longmemeval", "locomo", "convomem"):
            return filtered, f"Invalid suite: {suite!r}"
        be = str(filtered.get("backend", "fts5")).lower()
        if be not in ("fts5", "grep", "chromadb", "hybrid"):
            return filtered, f"Invalid backend: {be!r}"
        comp = str(filtered.get("compressor", "raw")).lower()
        if comp not in ("raw", "steno", "prune", "extract", "compact"):
            return filtered, f"Invalid compressor: {comp!r}"
    return filtered, None


def _maybe_truncate_json_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated by mcp.max_response_chars]"


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

    if method == "notifications/cancelled":
        rid = reason = None
        if isinstance(params, dict):
            rid = params.get("requestId")
            reason = params.get("reason")
        logger.info(
            _mcp_log_line("mcp notifications/cancelled", requestId=rid, reason=reason),
            extra=_mcp_log_extra(cancelled_request_id=rid, method="notifications/cancelled"),
        )
        # Single-threaded stdio: cannot interrupt an in-flight tool; client may still race.
        return None

    if method == "tools/list":
        active = get_active_tools()
        tool_list = [
            {"name": name, "description": t["description"], "inputSchema": t["input_schema"]}
            for name, t in active.items()
        ]
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tool_list}}

    if method == "tools/call":
        tool_name = params.get("name")
        raw_args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        active = get_active_tools()
        if tool_name not in active:
            logger.info(
                _mcp_log_line("mcp tools/call unknown tool", tool=tool_name),
                extra=_mcp_log_extra(request_id=req_id, method="tools/call", tool=str(tool_name)),
            )
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Unknown or disabled tool: {tool_name}"},
            }
        schema = active[tool_name]["input_schema"]
        tool_args, prep_err = _prepare_tool_arguments(tool_name, raw_args, schema)
        if prep_err:
            logger.info(
                _mcp_log_line("mcp tools/call invalid params", tool=tool_name, detail=prep_err),
                extra=_mcp_log_extra(request_id=req_id, method="tools/call", tool=str(tool_name)),
            )
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32602, "message": prep_err},
            }

        _t0 = time.monotonic()
        try:
            result = active[tool_name]["handler"](**tool_args)
            _elapsed = round((time.monotonic() - _t0) * 1000, 1)
            _metrics.record("mcp.tool_call", _elapsed, meta={"tool": tool_name}, tags=["mcp"])
            text = json.dumps(result, indent=2, default=str)
            try:
                max_c = int(_mcp_cfg().get("max_response_chars") or 0)
            except (TypeError, ValueError):
                max_c = 0
            text = _maybe_truncate_json_text(text, max_c)
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": text}]},
            }
        except Exception as e:
            logger.exception(
                _mcp_log_line("mcp tool error", tool=tool_name, request_id=req_id),
                extra=_mcp_log_extra(request_id=req_id, method="tools/call", tool=str(tool_name)),
            )
            _metrics.record("mcp.tool_error", 1, meta={"tool": tool_name, "error": str(e)[:200]}, tags=["mcp", "error"])
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32000, "message": _sanitize_tool_error_message(e)},
            }

    logger.info(
        _mcp_log_line("mcp unknown method", method=method, request_id=req_id),
        extra=_mcp_log_extra(request_id=req_id, method=str(method)),
    )
    return {
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


def main() -> None:
    logger.info("llm-wiki MCP server starting (vault: %s)...", _vault)
    while True:
        request: dict[str, Any] | None = None
        try:
            line = sys.stdin.readline()
            if not line:
                break
            if len(line) > _MAX_JSON_RPC_LINE_BYTES:
                logger.error(
                    _mcp_log_line(
                        "mcp stdin line too large",
                        max_bytes=_MAX_JSON_RPC_LINE_BYTES,
                        line_bytes=len(line),
                    ),
                    extra=_mcp_log_extra(),
                )
                continue
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
            logger.error(
                _mcp_log_line("mcp invalid JSON on stdin", error=str(e)),
                extra=_mcp_log_extra(),
            )
        except Exception:
            rid = request.get("id") if isinstance(request, dict) else None
            logger.exception(
                _mcp_log_line("mcp server loop error", request_id=rid),
                extra=_mcp_log_extra(request_id=rid),
            )


if __name__ == "__main__":
    main()
