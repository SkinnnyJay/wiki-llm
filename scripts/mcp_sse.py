#!/usr/bin/env python3
"""
HTTP JSON-RPC bridge for MCP (started with: llm-wiki mcp --transport sse).

The --transport sse flag name is a legacy convention; the actual protocol is
synchronous HTTP POST with JSON-RPC request/response (not Server-Sent Events).

Uses stdlib only. Clients POST a single JSON-RPC object; the response is returned
as application/json. Set LLM_WIKI_VAULT before importing mcp_server (done by run_sse_server).
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
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

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

    from mcp_server import _mcp_log_extra, _mcp_log_line, handle_request, logger

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
                    got = self.headers.get("X-LLM-Wiki-Token", "")
                if got != auth_token:
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
