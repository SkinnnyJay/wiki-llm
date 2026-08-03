"""MCP write / mutate tool handlers."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from lib.config_loader import load_config, save_config
from lib.knowledge_graph import get_kg_backend
from lib.metrics import get_metrics as factory_metrics
from lib.paths import plugin_root
from lib.search import get_search_backend

from mcp.ctx import (
    CONFIGURE_RESTART_KEYS,
    configure_key_allowed,
    get_cfg,
    get_search,
    mcp_cfg,
    no_vault,
    require_vault,
    safe_benchmark_data_path,
    set_cfg,
    set_kg,
    set_metrics,
    set_search,
    state_lock,
    vault_ok,
)


def tool_wiki_agent_diary_append(
    agent_id: str, line: str, source: str = ""
) -> dict[str, Any]:
    """Append one markdown bullet line to an agent diary."""
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    from lib.agent_diary import append_diary

    p = append_diary(vault, agent_id, line, source=source or None)
    return {"agent_id": agent_id, "path": str(p.relative_to(vault)), "ok": True}


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
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    if not bool(mcp_cfg().get("ingest_enabled", False)):
        return {"skipped": True, "reason": "mcp.ingest_enabled is false"}
    if force_security and not bool(mcp_cfg().get("allow_force_security", False)):
        return {
            "success": False,
            "error": "force_security requires mcp.allow_force_security=true",
        }
    from ingest.registry import LOCAL_PATH_ADAPTER_IDS, adapter_map, run_ingest
    from lib.ingest_finish import post_ingest

    if adapter in LOCAL_PATH_ADAPTER_IDS and not bool(
        mcp_cfg().get("allow_local_file_ingest", False)
    ):
        return {
            "success": False,
            "error": (
                f"adapter={adapter!r} reads a local host path; set "
                "mcp.allow_local_file_ingest=true to enable over MCP "
                "(CLI ingest remains unrestricted)"
            ),
        }

    adapters = adapter_map()
    if adapter not in adapters:
        return {"error": f"Unknown adapter: {adapter}", "available": list(adapters.keys())}
    argv = [source]
    if out:
        argv.extend(["--out", out])
    try:
        result = run_ingest(vault, get_cfg(), adapter, argv, force_adapter=force)
    except SystemExit as e:
        msg = str(e) if str(e) else (str(e.code) if isinstance(e.code, int) else "ingest failed")
        return {"success": False, "error": msg}
    except Exception as e:
        return {"success": False, "error": str(e)}
    manual_tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    try:
        exit_code = post_ingest(
            vault,
            get_cfg(),
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

def tool_wiki_build_site(if_stale: bool = False) -> dict[str, Any]:
    """Rebuild the static viewer. if_stale=true skips build when site is already current."""
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    from lib.sitegen import build_site, site_is_stale

    if if_stale and not site_is_stale(vault):
        return {"success": True, "skipped": True, "reason": "site up-to-date"}
    try:
        out = build_site(vault, get_cfg())
        return {"success": True, "output": str(out)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def tool_wiki_graph_build(mode: str = "links", out: str = "") -> dict[str, Any]:
    """Build D3 graph bundle (HTML/JS) — distinct from wiki_graph JSON."""
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    from lib.graphgen import build_graph_bundle
    from lib.path_safety import resolve_under

    m = str(mode).lower().strip()
    if m not in ("links", "knowledge"):
        return {"success": False, "error": 'mode must be "links" or "knowledge"'}
    # Allow writes only under vault/.tmp or plugin/.tmp (never arbitrary paths).
    default_out = (vault / ".tmp" / "llm-wiki-graph").resolve()
    if (out or "").strip():
        candidate = Path(out)
        out_dir = None
        for root in (vault.resolve(), plugin_root().resolve()):
            if candidate.is_absolute():
                try:
                    candidate.resolve().relative_to(root / ".tmp")
                    out_dir = candidate.resolve()
                    break
                except ValueError:
                    continue
            else:
                under = resolve_under(root / ".tmp", candidate)
                if under is not None:
                    out_dir = under
                    break
        if out_dir is None:
            return {
                "success": False,
                "error": "out must be under vault/.tmp or plugin/.tmp",
            }
    else:
        out_dir = default_out
    try:
        path = build_graph_bundle(vault, get_cfg(), out_dir, m)
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
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    rules = mcp_cfg().get("configure_allowlist") or []
    if not isinstance(rules, list):
        rules = []
    if not configure_key_allowed(key, rules):
        return {
            "success": False,
            "error": (
                "Key not allowed by mcp.configure_allowlist "
                "(empty allowlist denies mcp.*/security.*/storage.*/hooks.*, "
                "memory.dir, benchmark path dirs)"
            ),
            "key": key,
        }
    with state_lock():
        cfg = load_config(vault)
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
        save_config(vault, cfg)
        # Hot-reload in-process config so subsequent tools see the change.
        set_cfg(load_config(vault))
        restart_required = key in CONFIGURE_RESTART_KEYS or key.startswith("mcp.sse_")
        # Refresh search/KG backends when relevant knobs change.
        if key.startswith("mcp.search") or key.startswith("knowledge_graph.") or key == "knowledge_graph":
            metrics = factory_metrics(vault, get_cfg())
            set_metrics(metrics)
            search = get_search_backend(vault, get_cfg())
            search._metrics = metrics  # type: ignore[attr-defined]
            set_search(search)
            kg = get_kg_backend(vault, get_cfg())
            kg._metrics = metrics  # type: ignore[attr-defined]
            set_kg(kg)
        return {
            "success": True,
            "key": key,
            "value": parsed,
            "restart_required": restart_required,
            "hint": (
                "Restart the MCP process for transport/port/token changes to take effect"
                if restart_required
                else None
            ),
        }

def tool_wiki_reindex() -> dict[str, Any]:
    """Rebuild the search index from vault files."""
    if not vault_ok():
        return no_vault()
    return get_search().reindex()

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

    if not vault_ok():
        return no_vault()
    vault = require_vault()
    if not mem.memory_enabled(get_cfg()):
        return {"skipped": True, "reason": "memory.enabled is false"}
    try:
        sid = mem.resolve_current_session(vault) if current else session_id.strip()
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
        vault,
        get_cfg(),
        sid,
        summary=summary or None,
        compact_summary=compact_summary or None,
        tags=tag_list,
        metadata=meta,
    )
    return {"path": path.relative_to(vault).as_posix(), "ok": True}

def tool_memory_log(
    session_id: str = "",
    current: bool = False,
    message_preview: str = "",
) -> dict[str, Any]:
    """Append a conversation round to session memory. Prefer CLI when local."""
    from lib import session_memory as mem

    if not vault_ok():
        return no_vault()
    vault = require_vault()
    if not mem.memory_enabled(get_cfg()):
        return {"skipped": True, "reason": "memory.enabled is false"}
    try:
        sid = mem.resolve_current_session(vault) if current else session_id.strip()
        if not sid:
            return {"error": "Pass session_id or current=true"}
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    path = mem.memory_log_round(
        vault,
        get_cfg(),
        sid,
        message_preview=message_preview or None,
    )
    return {"path": path.relative_to(vault).as_posix(), "ok": True}

def tool_memory_prune(
    session_id: str = "",
    tag: str = "",
    older_than_days: int = 0,
    keep: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete session memory files."""
    from lib import session_memory as mem

    if not vault_ok():
        return no_vault()
    vault = require_vault()
    if not mem.memory_enabled(get_cfg()):
        return {"skipped": True, "reason": "memory.enabled is false"}
    try:
        out = mem.memory_prune(
            vault,
            get_cfg(),
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
    if not vault_ok():
        return no_vault()
    vault = require_vault()
    bcfg = get_cfg().get("benchmark") or {}
    if not bcfg.get("enabled", True):
        return {
            "error": "benchmark.enabled is false",
            "hint": "Set benchmark.enabled to true in config.json",
        }
    try:
        data_resolved = safe_benchmark_data_path(data_path)
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
        cfg_run = load_config(vault)
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
                        vault,
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
                vault,
                cfg_run,
                backend=be,
                compressor_name=compressor,
                limit=lim,
                top_k=tk,
            )
            fail_path = finalize_lme_run(
                vault,
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
                "summary": run_locomo(vault, cfg_run, limit=lim, data_path=data_resolved).get("summary", {})
            }
        if suite_norm == "convomem":
            from benchmarks.convomem_bench import run_convomem

            return {
                "summary": run_convomem(vault, cfg_run, limit=lim, data_path=data_resolved).get("summary", {})
            }
        return {"error": f"unknown suite: {suite}", "hint": "use lme | locomo | convomem"}
    finally:
        if old_llm is None:
            os.environ.pop("LLM_WIKI_BENCHMARK_LLM", None)
        else:
            os.environ["LLM_WIKI_BENCHMARK_LLM"] = old_llm


def tool_wiki_lint(
    schema: bool = False,
    check_stale: bool = True,
    check_outputs: bool = True,
) -> dict[str, Any]:
    """Deterministic wiki health lint (writes outputs/lint-report.json + claims when enabled)."""
    if not vault_ok():
        return no_vault()
    if not bool(mcp_cfg().get("compile_enabled", False)):
        return {"skipped": True, "reason": "mcp.compile_enabled is false"}
    vault = require_vault()
    from lib.wiki_lint import lint_vault, write_lint_report

    cfg = get_cfg()
    report = lint_vault(
        vault,
        cfg,
        check_schema=True if schema else None,
        check_stale=check_stale,
        check_outputs=check_outputs,
    )
    path = write_lint_report(vault, report)
    return {
        "ok": bool(report.get("ok")),
        "counts": report.get("counts"),
        "issues": report.get("issues", [])[:50],
        "report": str(path.relative_to(vault)),
    }


def tool_wiki_compile(
    schema: bool = False,
    no_kg: bool = False,
    no_site: bool = False,
    raw: str = "",
    stubs: bool = False,
) -> dict[str, Any]:
    """Run knowledge CI gates (validate + lint/claims + KG conflicts + optional site)."""
    if not vault_ok():
        return no_vault()
    if not bool(mcp_cfg().get("compile_enabled", False)):
        return {"skipped": True, "reason": "mcp.compile_enabled is false"}
    vault = require_vault()
    from lib.compile_pipeline import run_compile

    allow_site = bool(mcp_cfg().get("compile_allow_site", False))
    skip_site = bool(no_site) or not allow_site
    result = run_compile(
        vault,
        get_cfg(),
        skip_kg=bool(no_kg),
        skip_site=skip_site,
        strict_schema=bool(schema),
        json_out=False,
        raw_path=(raw or "").strip() or None,
        write_stubs=bool(stubs),
    )
    if not allow_site and not no_site:
        result = {
            **result,
            "site_note": "viewer rebuild skipped unless mcp.compile_allow_site=true",
        }
    return result

