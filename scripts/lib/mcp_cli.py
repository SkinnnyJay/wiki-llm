"""MCP enablement from vault config (shared by CLI and MCP server)."""

from __future__ import annotations

import sys
from typing import Any

# User-facing text when mcp.enabled is false (CLI stderr and server log).
MCP_DISABLED_MESSAGE = (
    "MCP server disabled in config.json (mcp.enabled=false). Enable it to start."
)


def mcp_enabled(cfg: dict[str, Any]) -> bool:
    """True when the MCP server is allowed to start (default: enabled)."""
    return (cfg.get("mcp") or {}).get("enabled", True)


def cli_exit_if_mcp_disabled(cfg: dict[str, Any]) -> int | None:
    """If MCP is disabled, print to stderr and return 1; else return None."""
    if mcp_enabled(cfg):
        return None
    print(MCP_DISABLED_MESSAGE, file=sys.stderr)
    return 1
