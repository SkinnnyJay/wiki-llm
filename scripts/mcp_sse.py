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
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Cap POST body size (Content-Length) to avoid memory exhaustion.
_MAX_HTTP_JSON_BYTES = 32 * 1024 * 1024


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
        print(
            "warning: mcp.sse_token is empty; HTTP MCP on loopback has no auth. "
            "Set mcp.sse_token for defense in depth.",
            file=sys.stderr,
        )

    from mcp import server as mcp_server
    import hmac

    if not mcp_server.initialize(vault, require_enabled=True):
        print("MCP is disabled in config.json.", file=sys.stderr)
        raise SystemExit(1)
    _mcp_log_extra = mcp_server._mcp_log_extra
    _mcp_log_line = mcp_server._mcp_log_line
    handle_request = mcp_server.handle_request
    logger = mcp_server.logger

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
                # Constant-time compare; pad lengths via hmac.compare_digest on equal-length utf-8
                try:
                    ok = hmac.compare_digest(got.encode("utf-8"), auth_token.encode("utf-8"))
                except (TypeError, ValueError):
                    ok = False
                if not ok:
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
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length > _MAX_HTTP_JSON_BYTES:
                err = json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32600,
                            "message": f"Content-Length exceeds {_MAX_HTTP_JSON_BYTES} bytes",
                        },
                    }
                ).encode("utf-8")
                self.send_response(413)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
                return
            raw = self.rfile.read(length) if length else b"{}"
            try:
                request = json.loads(raw.decode("utf-8"))
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
            try:
                response = handle_request(request)
            except Exception:
                rid = request.get("id") if isinstance(request, dict) else None
                meth = request.get("method") if isinstance(request, dict) else None
                logger.exception(
                    _mcp_log_line("mcp http handle_request failed", request_id=rid, method=meth),
                    extra=_mcp_log_extra(request_id=rid, method=str(meth) if meth else None),
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

    httpd = ThreadingHTTPServer((host, port), MCPHTTPHandler)
    logger.info("llm-wiki MCP HTTP listening on http://%s:%s/ (POST JSON-RPC)", host, port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
