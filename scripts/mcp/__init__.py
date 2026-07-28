"""Public MCP runtime API.

The executable shim remains at :mod:`mcp_server` for installed plugin
configurations; new embedded consumers should import this package instead.
"""

from mcp.server import handle_request, initialize, main, set_metrics

__all__ = ["handle_request", "initialize", "main", "set_metrics"]
