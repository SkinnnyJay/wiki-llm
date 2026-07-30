"""MCP tool visibility rules shared by stdio and embedded transports."""

from __future__ import annotations

from typing import Any


def build_active_tools(
    cfg: dict[str, Any],
    registry: dict[str, dict[str, Any]],
    read_only_names: frozenset[str],
) -> dict[str, dict[str, Any]]:
    """Filter tools according to MCP mode, explicit allowlists, and feature gates."""
    mcp = cfg.get("mcp") or {}
    out = dict(registry)
    if not bool(mcp.get("benchmark_tool_enabled", True)):
        out.pop("wiki_benchmark_run", None)
        out.pop("wiki_benchmark_suites", None)
    if not bool(mcp.get("ingest_enabled", True)):
        out.pop("wiki_ingest", None)
    if not bool(mcp.get("compile_enabled", False)):
        out.pop("wiki_compile", None)
        out.pop("wiki_lint", None)
    mode = str(mcp.get("tools_mode") or "full").strip().lower()
    allow = mcp.get("tools_allowlist") or []
    if not isinstance(allow, list):
        allow = []
    if mode == "full":
        return out
    if mode == "read_only":
        return {name: tool for name, tool in out.items() if name in read_only_names}
    if mode == "custom":
        allowed_names = read_only_names if not allow else frozenset(map(str, allow))
        return {name: tool for name, tool in out.items() if name in allowed_names}
    return out
