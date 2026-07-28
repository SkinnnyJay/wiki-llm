"""Lazy public facade for the MCP stdio protocol and tool registry.

``mcp_server.py`` remains the executable compatibility entry point. Keeping
imports here lazy lets applications import ``mcp`` without starting services or
exiting merely because a vault has MCP disabled.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _legacy() -> Any:
    import mcp_server

    return mcp_server


def initialize(
    vault: Path | None = None, *, require_enabled: bool = False
) -> bool:
    """Initialize the configured vault on demand."""
    return _legacy().initialize(vault, require_enabled=require_enabled)


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    """Handle one MCP JSON-RPC request."""
    return _legacy().handle_request(request)


def set_metrics(metrics: Any) -> None:
    """Set the active metrics recorder for embedded use and tests."""
    _legacy().set_metrics(metrics)


def main() -> None:
    """Run the backward-compatible stdio server."""
    _legacy().main()


def __getattr__(name: str) -> Any:
    """Expose logging and registry helpers without eager runtime initialization."""
    return getattr(_legacy(), name)
