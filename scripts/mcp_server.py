#!/usr/bin/env python3
"""
llm-wiki MCP Server — stdio JSON-RPC transport (zero external deps).

Install:
  claude mcp add llm-wiki -- python3 /path/to/wiki-llm/scripts/mcp_server.py [--vault /path/to/vault]

Exposes vault read, write, search, and knowledge-graph tools over MCP.

Tool handlers live under :mod:`mcp.tools_read`, :mod:`mcp.tools_kg`, and
:mod:`mcp.tools_write`. Runtime state is :mod:`mcp.ctx`.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.mcp_cli import MCP_DISABLED_MESSAGE, mcp_enabled
from lib.version import __version__
from mcp import ctx as _ctx
from mcp.tools_kg import (
    tool_wiki_find_connections,
    tool_wiki_kg_add,
    tool_wiki_kg_invalidate,
    tool_wiki_kg_query,
    tool_wiki_kg_rebuild,
    tool_wiki_kg_stats,
    tool_wiki_kg_timeline,
    tool_wiki_kg_traverse,
)
from mcp.tools_read import (
    tool_memory_list,
    tool_memory_recall,
    tool_memory_show,
    tool_wiki_agent_diary_read,
    tool_wiki_benchmark_suites,
    tool_wiki_check_duplicate,
    tool_wiki_doctor,
    tool_wiki_find_related,
    tool_wiki_git_status,
    tool_wiki_graph,
    tool_wiki_list_topics,
    tool_wiki_metrics_query,
    tool_wiki_metrics_stats,
    tool_wiki_raw_validate,
    tool_wiki_read_page,
    tool_wiki_search,
    tool_wiki_search_index_status,
    tool_wiki_status,
    tool_wiki_validate,
    tool_wiki_wake_up,
)
from mcp.tools_registry import READ_ONLY_TOOL_NAMES, TOOLS
from mcp.tools_write import (
    tool_memory_log,
    tool_memory_prune,
    tool_memory_save,
    tool_wiki_agent_diary_append,
    tool_wiki_benchmark_run,
    tool_wiki_build_site,
    tool_wiki_configure,
    tool_wiki_graph_build,
    tool_wiki_ingest,
    tool_wiki_reindex,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [llm-wiki-mcp] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("llm_wiki_mcp")

# Advertise the current stable protocol while retaining the prior version for
# clients that only negotiate that revision. Do not advertise unreleased dates.
MCP_PROTOCOL_VERSION = "2025-11-25"
MCP_LEGACY_PROTOCOL_VERSION = "2024-11-05"
MCP_SUPPORTED_PROTOCOL_VERSIONS = frozenset(
    {MCP_PROTOCOL_VERSION, MCP_LEGACY_PROTOCOL_VERSION}
)

# Reject absurdly large JSON-RPC lines (DoS / accidental paste) — stdio transport.
_MAX_JSON_RPC_LINE_BYTES = 32 * 1024 * 1024


def _mcp_log_extra(
    *,
    request_id: str | int | float | None = None,
    method: str | None = None,
    tool: str | None = None,
    cancelled_request_id: str | int | float | None = None,
) -> dict[str, str | int | float]:
    """Keyword fields merged into LogRecord (for aggregators); keys avoid LogRecord builtins."""
    d: dict[str, str | int | float] = {}
    if request_id is not None:
        d["mcp_request_id"] = request_id
    if method:
        d["mcp_method"] = method
    if tool:
        d["mcp_tool"] = tool
    if cancelled_request_id is not None:
        d["mcp_cancelled_request_id"] = cancelled_request_id
    return d


def _mcp_log_line(msg: str, **fields: object) -> str:
    """Human-readable suffix with key=value pairs for stderr (works without custom formatters)."""
    tail = " ".join(f"{k}={v!r}" for k, v in fields.items() if v is not None)
    return f"{msg} | {tail}" if tail else msg


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="llm-wiki MCP server")
    p.add_argument("--vault", metavar="PATH", help="Override vault path")
    args, _ = p.parse_known_args()
    return args


# Compatibility aliases — same objects as mcp.ctx (tests may patch either).
_vault = _ctx._vault
_cfg = _ctx._cfg
_metrics = _ctx._metrics
_search = _ctx._search
_kg = _ctx._kg


def _sync_aliases_from_ctx() -> None:
    global _vault, _cfg, _metrics, _search, _kg
    _vault = _ctx._vault
    _cfg = _ctx._cfg
    _metrics = _ctx._metrics
    _search = _ctx._search
    _kg = _ctx._kg


def _sync_aliases_to_ctx() -> None:
    """Push mcp_server aliases into ctx (for tests that patch this module)."""
    _ctx._vault = _vault
    _ctx._cfg = _cfg
    _ctx._metrics = _metrics
    _ctx._search = _search
    _ctx._kg = _kg


def _require_vault() -> Path:
    return _ctx.require_vault()


def _no_vault() -> dict[str, Any]:
    return _ctx.no_vault()


def _vault_ok() -> bool:
    _sync_aliases_to_ctx()
    return _ctx.vault_ok()


def _mcp_cfg() -> Any:
    _sync_aliases_to_ctx()
    return _ctx.mcp_cfg()


def initialize(
    vault: Path | None = None, *, require_enabled: bool = False
) -> bool:
    """Initialize vault-backed services on first use.

    Importing this module is intentionally side-effect free so library consumers
    can inspect or reuse the MCP protocol even when ``mcp.enabled`` is false.
    Entry points pass ``require_enabled=True`` and retain the historical
    non-zero exit behavior.
    """
    if _ctx._vault is not None and (vault is None or _ctx._vault.resolve() == vault.resolve()):
        _sync_aliases_from_ctx()
        return mcp_enabled(_ctx._cfg)

    if vault is not None:
        _ctx.init_runtime(vault=vault)
    else:
        args = _parse_args()
        _ctx.init_runtime(vault_override=args.vault)
    _sync_aliases_from_ctx()
    return mcp_enabled(_ctx._cfg)


def set_metrics(metrics: Any) -> None:
    """Replace the active metrics recorder (primarily for embedding and tests)."""
    _ctx.set_metrics(metrics)
    _sync_aliases_from_ctx()


def build_active_tools(
    cfg: dict[str, Any], registry: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Filter the registry according to MCP mode and feature gates."""
    from mcp.registry import build_active_tools as _build_active_tools

    return _build_active_tools(cfg, registry, READ_ONLY_TOOL_NAMES)


def get_active_tools() -> dict[str, dict[str, Any]]:
    _sync_aliases_to_ctx()
    return build_active_tools(_ctx._cfg, TOOLS)


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


def _negotiated_protocol_version(params: object) -> str:
    """Use the client's supported legacy revision when it explicitly requests it."""
    if isinstance(params, dict) and params.get("protocolVersion") == MCP_LEGACY_PROTOCOL_VERSION:
        return MCP_LEGACY_PROTOCOL_VERSION
    return MCP_PROTOCOL_VERSION


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    if not initialize():
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {"code": -32000, "message": MCP_DISABLED_MESSAGE},
        }
    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": _negotiated_protocol_version(params),
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
            _sync_aliases_to_ctx()
            result = active[tool_name]["handler"](**tool_args)
            _elapsed = round((time.monotonic() - _t0) * 1000, 1)
            metrics = _ctx.get_metrics()
            if metrics is not None:
                metrics.record("mcp.tool_call", _elapsed, meta={"tool": tool_name}, tags=["mcp"])
            text = json.dumps(result, indent=2, default=str)
            try:
                max_c = int(_ctx.mcp_cfg().get("max_response_chars") or 0)
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
            metrics = _ctx.get_metrics()
            if metrics is not None:
                metrics.record(
                    "mcp.tool_error",
                    1,
                    meta={"tool": tool_name, "error": str(e)[:200]},
                    tags=["mcp", "error"],
                )
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
    if not initialize(require_enabled=True):
        logger.error(MCP_DISABLED_MESSAGE)
        raise SystemExit(1)
    vault = _require_vault()
    logger.info("llm-wiki MCP server starting (vault: %s)...", vault)
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
            parsed = json.loads(line)
            if not isinstance(parsed, dict):
                continue
            request = parsed
            response = handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except KeyboardInterrupt:
            break
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON: %s", e)
        except Exception:
            logger.exception(
                _mcp_log_line("mcp request failed", request_id=(request or {}).get("id")),
                extra=_mcp_log_extra(request_id=(request or {}).get("id")),
            )


if __name__ == "__main__":
    main()
