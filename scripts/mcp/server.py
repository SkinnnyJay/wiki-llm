"""Lazy public facade for the MCP stdio protocol and tool registry.

``mcp_server.py`` remains the executable compatibility entry point. Keeping
imports here lazy lets applications import ``mcp`` without starting services or
exiting merely because a vault has MCP disabled.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol, TypeAlias, cast

MCPRequestId: TypeAlias = str | int | float | None
MCPLogExtra: TypeAlias = dict[str, str | int | float]


class _LegacyMCPServer(Protocol):
    """Typed surface consumed by this lazy compatibility facade."""

    logger: logging.Logger

    def initialize(self, vault: Path | None = None, *, require_enabled: bool = False) -> bool: ...

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None: ...

    def _mcp_log_extra(
        self,
        *,
        request_id: MCPRequestId = None,
        method: str | None = None,
    ) -> MCPLogExtra: ...

    def _mcp_log_line(self, msg: str, **fields: object) -> str: ...

    def set_metrics(self, metrics: object) -> None: ...

    def main(self) -> None: ...


def _legacy() -> _LegacyMCPServer:
    import mcp_server

    return cast(_LegacyMCPServer, mcp_server)


def initialize(
    vault: Path | None = None, *, require_enabled: bool = False
) -> bool:
    """Initialize the configured vault on demand."""
    return _legacy().initialize(vault, require_enabled=require_enabled)


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    """Handle one MCP JSON-RPC request."""
    return _legacy().handle_request(request)


def log_extra(
    *,
    request_id: MCPRequestId = None,
    method: str | None = None,
) -> MCPLogExtra:
    """Return structured logging fields for an HTTP JSON-RPC request."""
    return _legacy()._mcp_log_extra(request_id=request_id, method=method)


def log_line(msg: str, **fields: object) -> str:
    """Format a human-readable MCP log line without exposing private helpers."""
    return _legacy()._mcp_log_line(msg, **fields)


def get_logger() -> logging.Logger:
    """Return the MCP protocol logger without exposing the lazy legacy module."""
    return _legacy().logger


def set_metrics(metrics: object) -> None:
    """Set the active metrics recorder for embedded use and tests."""
    _legacy().set_metrics(metrics)


def main() -> None:
    """Run the backward-compatible stdio server."""
    _legacy().main()


def __getattr__(name: str) -> object:
    """Expose logging and registry helpers without eager runtime initialization."""
    return cast(object, getattr(_legacy(), name))
