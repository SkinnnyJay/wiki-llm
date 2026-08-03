"""Availability boundaries for the HTTP MCP bridge."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from mcp_sse import BoundedMCPHTTPServer


class _FakeRequest:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_mcp_http_server_rejects_connections_when_worker_capacity_is_full() -> None:
    server = BoundedMCPHTTPServer(
        ("127.0.0.1", 0),
        BaseHTTPRequestHandler,
        max_workers=1,
    )
    request = _FakeRequest()
    try:
        assert server._worker_slots.acquire(blocking=False)

        server.process_request(request, ("127.0.0.1", 12345))

        assert request.closed is True
    finally:
        server._worker_slots.release()
        server.server_close()
