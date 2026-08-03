#!/usr/bin/env python3
"""
HTTP JSON-RPC bridge for MCP (started with: llm-wiki mcp --transport sse).

The --transport sse flag name is a legacy convention; the actual protocol is
synchronous HTTP POST with JSON-RPC request/response (not Server-Sent Events).

Uses stdlib only. Clients POST a single JSON-RPC object; the response is returned
as application/json.
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

# Cap POST body size (Content-Length) to avoid memory exhaustion.
_MAX_HTTP_JSON_BYTES = 32 * 1024 * 1024
MCP_HTTP_MAX_WORKERS = 32
MCP_HTTP_CLIENT_TIMEOUT_SECONDS = 15.0


class BoundedMCPHTTPServer(ThreadingHTTPServer):
    """Threaded HTTP server with bounded concurrent work and read timeouts."""

    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler: type[BaseHTTPRequestHandler],
        *,
        max_workers: int = MCP_HTTP_MAX_WORKERS,
    ) -> None:
        if max_workers <= 0:
            raise ValueError("max_workers must be positive")
        self._worker_slots = threading.BoundedSemaphore(max_workers)
        super().__init__(server_address, request_handler)

    def get_request(self) -> tuple[socket.socket, tuple[str, int]]:
        request, client_address = cast(
            tuple[socket.socket, tuple[str, int]],
            super().get_request(),
        )
        request.settimeout(MCP_HTTP_CLIENT_TIMEOUT_SECONDS)
        return request, client_address

    def process_request(self, request: socket.socket, client_address: tuple[str, int]) -> None:
        if not self._worker_slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._worker_slots.release()
            raise

    def process_request_thread(self, request: socket.socket, client_address: tuple[str, int]) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._worker_slots.release()


def run_sse_server(
    vault: Path,
    port: int,
    host: str = "127.0.0.1",
) -> None:
    """Listen for POST / and POST /mcp with JSON-RPC bodies; print URL on stderr."""
    os.environ["LLM_WIKI_VAULT"] = str(vault.resolve())

    from lib.config_loader import load_config

    cfg = load_config(vault)
    mcp_cfg = cfg.get("mcp") or {}
    require_lo = bool(mcp_cfg.get("sse_require_loopback", True))
    if require_lo:
        ok = False
        hl = host.strip().lower()
        if hl in ("localhost", "::1", "127.0.0.1"):
            ok = True
        else:
            try:
                ok = ipaddress.ip_address(host).is_loopback
            except ValueError:
                ok = False
        if not ok:
            print(
                f"mcp.sse_require_loopback is true but host {host!r} is not loopback. "
                "Set mcp.sse_require_loopback to false only with firewall/TLS/proxy.",
                file=sys.stderr,
            )
            sys.exit(1)

    auth_token = str(mcp_cfg.get("sse_token") or "").strip()
    allow_empty = bool(mcp_cfg.get("sse_allow_empty_token", False))
    host_is_loopback = False
    hl = host.strip().lower()
    if hl in ("localhost", "::1", "127.0.0.1"):
        host_is_loopback = True
    else:
        try:
            host_is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            host_is_loopback = False
    if not auth_token and not allow_empty and not host_is_loopback:
        print(
            "mcp.sse_token is empty but host is not loopback. "
            "Set mcp.sse_token, bind to 127.0.0.1, or set mcp.sse_allow_empty_token=true "
            "(insecure).",
            file=sys.stderr,
        )
        sys.exit(1)
    if not auth_token and host_is_loopback and not allow_empty:
        tools_mode = str(mcp_cfg.get("tools_mode") or "full").strip().lower()
        if tools_mode not in ("read_only", "readonly"):
            print(
                "error: mcp.sse_token is empty while tools_mode allows writes. "
                "Set mcp.sse_token, set mcp.tools_mode=read_only, or set "
                "mcp.sse_allow_empty_token=true (insecure).",
                file=sys.stderr,
            )
            sys.exit(1)
        print(
            "warning: mcp.sse_token is empty; HTTP MCP on loopback has no auth "
            "(tools_mode=read_only).",
            file=sys.stderr,
        )

    import hashlib
    import hmac

    from mcp import server as mcp_server

    if not mcp_server.initialize(vault, require_enabled=True):
        print("MCP is disabled in config.json.", file=sys.stderr)
        raise SystemExit(1)
    handle_request = mcp_server.handle_request
    log_extra = mcp_server.log_extra
    log_line = mcp_server.log_line
    logger = mcp_server.get_logger()

    def _token_ok(got: str) -> bool:
        """Compare tokens via SHA-256 digests to avoid length leaks."""
        dig_got = hashlib.sha256(got.encode("utf-8")).digest()
        dig_want = hashlib.sha256(auth_token.encode("utf-8")).digest()
        return hmac.compare_digest(dig_got, dig_want)

    class MCPHTTPHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if self.path not in ("/", "/mcp"):
                self.send_error(404, "POST / or /mcp only")
                return
            if auth_token:
                auth = self.headers.get("Authorization", "")
                got = ""
                if auth.lower().startswith("bearer "):
                    got = auth[7:].strip()
                if not got:
                    got = self.headers.get("X-LLM-Wiki-Token", "") or ""
                if not _token_ok(got):
                    body = json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {"code": -32000, "message": "Unauthorized"},
                        }
                    ).encode("utf-8")
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                length = -1
            if length < 0 or length > _MAX_HTTP_JSON_BYTES:
                err = json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32600,
                            "message": (
                                "Invalid or oversized Content-Length "
                                f"(max {_MAX_HTTP_JSON_BYTES} bytes)"
                            ),
                        },
                    }
                ).encode("utf-8")
                self.send_response(413 if length > _MAX_HTTP_JSON_BYTES else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
                return
            raw = self.rfile.read(length) if length else b"{}"
            try:
                decoded = cast(object, json.loads(raw.decode("utf-8")))
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Invalid JSON"}}
                    ).encode()
                )
                return
            if not isinstance(decoded, dict):
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "error": {"code": -32600, "message": "JSON-RPC request must be an object"},
                        }
                    ).encode()
                )
                return
            request = cast(dict[str, Any], decoded)
            try:
                response = handle_request(request)
            except Exception:
                raw_request_id = request.get("id")
                rid = (
                    raw_request_id
                    if isinstance(raw_request_id, (str, int, float)) and not isinstance(raw_request_id, bool)
                    else None
                )
                raw_method = request.get("method")
                meth = raw_method if isinstance(raw_method, str) else None
                logger.exception(
                    log_line("mcp http handle_request failed", request_id=rid, method=meth),
                    extra=log_extra(request_id=rid, method=meth),
                )
                response = {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {"code": -32000, "message": "Server error — see logs"},
                }
            if response is None:
                # JSON-RPC notifications: no response body (MCP cancel / initialized).
                self.send_response(204)
                self.end_headers()
                return
            body = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            logger.debug("%s - %s", self.address_string(), fmt % args)

    httpd = BoundedMCPHTTPServer((host, port), MCPHTTPHandler)
    logger.info("llm-wiki MCP HTTP listening on http://%s:%s/ (POST JSON-RPC)", host, port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
