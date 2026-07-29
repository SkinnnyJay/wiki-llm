"""MCP read / query tool handlers."""
from __future__ import annotations

import json
import sys
from typing import Any

from lib.config_loader import storage_warnings
from lib.doctor import doctor_report
from lib.paths import plugin_root

from mcp.ctx import (
    cached_md_counts,
    get_cfg,
    get_search,
    mcp_cfg,
    metrics_recorder_for_read,
    no_vault,
    require_vault,
    vault_ok,
)

def tool_wiki_wake_up() -> dict[str, Any]:
    """Load L0+L1 context blob for the vault — persona, topics, recent activity."""
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    from lib.layers import build_wake_up
    return {"context": build_wake_up(vault, get_cfg())}

def tool_wiki_status() -> dict[str, Any]:
    """Vault overview: file counts, config, backend modes, health."""
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    raw_count, wiki_count = cached_md_counts()
    mcp_slice = get_cfg().get("mcp") or {}
    kg_cfg = get_cfg().get("knowledge_graph") or {}
    idx = get_search().index_status()
    configured_sb = mcp_slice.get("search_backend", "fts5")
    active_sb = idx.get("backend", "?")
    fallback = (configured_sb == "chromadb" and active_sb == "grep") or (
        configured_sb == "hybrid" and active_sb == "fts5"
    )
    sw = storage_warnings(vault, get_cfg())
    out: dict[str, Any] = {
        "vault_path": str(vault),
        "raw_files": raw_count,
        "wiki_pages": wiki_count,
        "persona": (get_cfg().get("persona") or {}).get("name", "Gennie"),
        "search_backend": configured_sb,
        "search_backend_active": active_sb,
        "search_backend_fallback": fallback,
        "kg_backend": kg_cfg.get("backend", "json"),
        "git_enabled": (get_cfg().get("git") or {}).get("enabled", False),
    }
    if sw:
        out["storage_warnings"] = sw
    return out

def tool_wiki_doctor() -> dict[str, Any]:
    """Run the same non-mutating checks as ``llm-wiki doctor``."""
    vault = require_vault()
    return doctor_report(vault)

def tool_wiki_list_topics() -> dict[str, Any]:
    """Tag index with wiki coverage markers."""
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    tags_path = vault / "raw" / ".tags.json"
    if not tags_path.exists():
        return {"topics": [], "hint": "No tag index. Run: llm-wiki ingest ... --tags <topics>"}
    index = json.loads(tags_path.read_text(encoding="utf-8"))
    from lib.layers import wiki_page_for_tag
    topics = []
    for tag, files in sorted(index.items(), key=lambda kv: -len(kv[1])):
        wp = wiki_page_for_tag(vault, tag)
        topics.append({
            "tag": tag,
            "raw_files": len(files),
            "wiki_page": wp,
            "has_wiki": wp is not None,
        })
    return {"topics": topics}

def tool_wiki_validate() -> dict[str, Any]:
    """Vault health check — returns list of issues (empty = healthy)."""
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    errs: list[str] = []
    for p in [vault / "config.json", vault / "wiki" / "index.md", vault / "CLAUDE.md"]:
        if not p.is_file():
            errs.append(f"missing {p.relative_to(vault)}")
    return {"valid": len(errs) == 0, "issues": errs}


def tool_wiki_knowledge_test(file: str = "") -> dict[str, Any]:
    """Run knowledge regression tests against wiki/ (contains/absent assertions)."""
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    from pathlib import Path

    from lib.knowledge_tests import load_knowledge_tests, run_knowledge_tests
    from lib.paths import plugin_root

    path = Path(file) if file else Path()
    if not path.is_file():
        candidates = [
            vault / "knowledge-tests.json",
            vault / "outputs" / "knowledge-tests.json",
            plugin_root() / "examples" / "knowledge-tests.json",
        ]
        for c in candidates:
            if c.is_file():
                path = c
                break
    if not path.is_file():
        return {
            "ok": False,
            "error": "No knowledge-tests JSON found (pass file= or add vault knowledge-tests.json)",
        }
    tests = load_knowledge_tests(path)
    report = run_knowledge_tests(vault, tests)
    report["file"] = str(path)
    return report


def tool_wiki_read_page(path: str, max_chars: int = 0) -> dict[str, Any]:
    """Read markdown + frontmatter from a wiki/, raw/, or outputs/ file."""
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    from lib.path_safety import resolve_under_vault

    full = resolve_under_vault(vault, path)
    if full is None:
        return {"error": "Path escapes vault"}
    try:
        rel = full.resolve().relative_to(vault.resolve())
    except ValueError:
        return {"error": "Path escapes vault"}
    top = rel.parts[0] if rel.parts else ""
    if top not in ("wiki", "raw", "outputs"):
        return {
            "error": (
                "wiki_read_page only allows paths under wiki/, raw/, or outputs/ "
                "(refusing config and other vault roots)"
            ),
        }
    if not full.is_file():
        return {"error": f"File not found: {path}"}
    text = full.read_text(encoding="utf-8", errors="replace")
    from lib.search import _parse_frontmatter, _title_from, _tags_for_file
    fm, body = _parse_frontmatter(text)
    if max_chars is not None and max_chars != 0:
        lim = int(max_chars)
    else:
        lim = int(mcp_cfg().get("read_page_max_chars") or 0)
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
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    from lib.sitegen import collect_wiki
    raw = collect_wiki(vault, get_cfg())
    nodes = [{"id": n["id"], "title": n.get("title", n["id"]), "path": n.get("path")} for n in raw.get("nodes", [])]
    return {"nodes": nodes, "edges": raw.get("edges", []), "count": len(nodes)}

def tool_wiki_git_status() -> dict[str, Any]:
    """Vault git state."""
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    if not (get_cfg().get("git") or {}).get("enabled"):
        return {"enabled": False, "hint": "Git disabled in config.json"}
    from lib import git as vgit
    try:
        status = vgit.git_status(vault, get_cfg())
        return {"enabled": True, "status": status}
    except vgit.GitDisabledError as e:
        return {"enabled": False, "error": str(e)}

def tool_wiki_search(
    query: str,
    limit: int = 5,
    tag: str = "",
    scope: str = "wiki",
    wing: str = "",
    room: str = "",
) -> dict[str, Any]:
    """Search the vault. Default scope=wiki (compiled knowledge); use raw/all for evidence."""
    if not vault_ok():
        return no_vault()
    results = get_search().search(
        query,
        limit=limit,
        tag=tag or None,
        scope=scope,
        wing=wing or None,
        room=room or None,
    )
    return {"results": [r.to_dict() for r in results], "count": len(results), "backend": get_search().index_status().get("backend", "unknown")}

def tool_wiki_find_related(page_path: str, limit: int = 5) -> dict[str, Any]:
    """Find pages semantically similar to a given page."""
    if not vault_ok():
        return no_vault()
    results = get_search().find_related(page_path, limit=limit)
    return {"results": [r.to_dict() for r in results], "count": len(results)}

def tool_wiki_search_index_status() -> dict[str, Any]:
    """Show search index stats."""
    return get_search().index_status()

def tool_wiki_check_duplicate(content: str = "", path: str = "") -> dict[str, Any]:
    """Return paths with same content hash as the given body or file (ingest dedup index)."""
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    from ingest.dedup import check_duplicate, content_hash, strip_llm_wiki_keys
    from lib.path_safety import resolve_under_vault

    if path:
        p = resolve_under_vault(vault, path)
        if p is None:
            return {"error": "Path escapes vault"}
        if not p.is_file():
            return {"error": f"not a file: {path}"}
        text = p.read_text(encoding="utf-8", errors="replace")
        h = content_hash(strip_llm_wiki_keys(text))
    elif content:
        h = content_hash(content)
    else:
        return {"error": "provide content or path"}
    dupes = check_duplicate(vault, h)
    rels: list[str] = []
    for x in dupes:
        try:
            rels.append(str(x.relative_to(vault)))
        except ValueError:
            rels.append(str(x))
    return {"content_hash": h, "duplicates": rels, "count": len(rels)}

def tool_wiki_agent_diary_read(agent_id: str, max_chars: int = 8000) -> dict[str, Any]:
    """Read per-agent diary under raw/agents/<id>/diary.md."""
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    from lib.agent_diary import read_diary

    text = read_diary(vault, agent_id, max_chars=max_chars or 0)
    return {"agent_id": agent_id, "text": text, "chars": len(text)}

def tool_wiki_raw_validate(path: str, autofix: bool = False) -> dict[str, Any]:
    """Validate a raw/ file (optional deterministic autofix, same as CLI)."""
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    mode = str((mcp_cfg().get("tools_mode") or "full")).strip().lower()
    if autofix and mode == "read_only":
        return {
            "error": "autofix is not allowed when mcp.tools_mode is read_only",
            "hint": "Call without autofix, or use tools_mode full",
        }
    from lib.raw_validate import validate_raw_file_result

    r = validate_raw_file_result(vault, get_cfg(), path, autofix=autofix)
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

def tool_wiki_metrics_stats() -> dict[str, Any]:
    """Operational metrics summary (same data as `llm-wiki metrics stats`)."""
    if not vault_ok():
        return no_vault()
    m = metrics_recorder_for_read()
    return {"stats": m.stats()}

def tool_wiki_metrics_query(key: str = "", since: str = "", limit: int = 100) -> dict[str, Any]:
    """Query metrics records (read-only; use CLI for record/clear/report)."""
    if not vault_ok():
        return no_vault()
    m = metrics_recorder_for_read()
    records = m.query(key=key or None, since=since or None, limit=int(limit))
    return {"records": records, "count": len(records)}

def tool_wiki_benchmark_suites() -> dict[str, Any]:
    """Describe benchmark suites (same text as `llm-wiki benchmark suites`)."""
    if not vault_ok():
        return no_vault()
    root = plugin_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from benchmarks.suite_help import describe_benchmark_suites

    return {"text": describe_benchmark_suites()}

def tool_memory_list(session_id: str = "", tag: str = "") -> dict[str, Any]:
    """List session memory files."""
    from lib import session_memory as mem

    if not vault_ok():
        return no_vault()
    vault = require_vault()
    rows = mem.memory_list(vault, get_cfg(), session_id=session_id or None, tag=tag or None)
    return {"sessions": rows, "count": len(rows)}

def tool_memory_show(session_id: str = "", current: bool = False) -> dict[str, Any]:
    """Read one session memory file."""
    from lib import session_memory as mem

    if not vault_ok():
        return no_vault()
    vault = require_vault()
    try:
        sid = mem.resolve_current_session(vault) if current else session_id.strip()
        if not sid:
            return {"error": "Pass session_id or current=true"}
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    try:
        text = mem.memory_show(vault, get_cfg(), sid)
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

    if not vault_ok():
        return no_vault()
    vault = require_vault()
    if not query.strip():
        return {"error": "query required"}
    sf = None
    if current:
        try:
            sf = mem.resolve_current_session(vault)
        except (ValueError, FileNotFoundError) as e:
            return {"error": str(e)}
    elif session_id.strip():
        sf = session_id.strip()
    results = mem.memory_recall(
        vault,
        get_cfg(),
        query.strip(),
        session_id=sf,
        tag=tag or None,
        limit=limit,
    )
    return {"results": [r.to_dict() for r in results], "count": len(results)}

