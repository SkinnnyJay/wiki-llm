#!/usr/bin/env python3
"""
HTTP JSON-RPC bridge for MCP (started with: llm-wiki mcp --transport sse).

Uses stdlib only. Clients POST a single JSON-RPC object; the response is returned
as application/json. Set LLM_WIKI_VAULT before importing mcp_server (done by run_sse_server).
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
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

    from mcp_server import handle_request, logger

    class MCPHTTPHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if self.path not in ("/", "/mcp"):
                self.send_error(404, "POST / or /mcp only")
                return
            length = int(self.headers.get("Content-Length", "0") or 0)
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
                if response is None:
                    response = {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "result": {},
                    }
            except Exception as e:
                logger.exception("handle_request")
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {"code": -32000, "message": str(e)},
                }
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
