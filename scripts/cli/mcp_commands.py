"""MCP server CLI (stdio / SSE) and install."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.config_loader import load_config
from lib.mcp_cli import cli_exit_if_mcp_disabled
from lib.paths import plugin_root, resolve_vault

# ── MCP server ───────────────────────────────────────────────────────────────

def _mcp_tcp_listening(host: str, port: int, *, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _terminate_child_process(proc: subprocess.Popen, *, wait_s: float = 5.0) -> None:
    """Stop a child started for MCP HTTP; no-op if already exited."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=wait_s)
    except subprocess.TimeoutExpired:
        proc.kill()


def _mcp_start_background(args: argparse.Namespace) -> int:
    """
    Ensure the HTTP (SSE) MCP listener is running: if nothing is bound on the
    configured host/port, spawn ``llm-wiki mcp --transport sse`` in the background.
    """
    vault = resolve_vault(override=getattr(args, "vault", None))
    cfg = load_config(vault)
    blocked = cli_exit_if_mcp_disabled(cfg)
    if blocked is not None:
        return blocked

    mcp_cfg = cfg.get("mcp") or {}
    port = getattr(args, "mcp_port", None)
    if port is None:
        port = int(mcp_cfg.get("port") or 8891)
    host = getattr(args, "mcp_host", None) or mcp_cfg.get("host") or "127.0.0.1"
    host = str(host)

    url = f"http://{host}:{port}/"
    if _mcp_tcp_listening(host, port):
        print(f"MCP HTTP already listening — {url}")
        return 0

    lock_path = vault / ".mcp-sse-start.lock"
    lock_fd = open(lock_path, "a+", encoding="utf-8")
    try:
        if sys.platform == "win32":
            import msvcrt

            # Exclusive lock for the whole file (blocking).
            while True:
                try:
                    lock_fd.seek(0)
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
        else:
            import fcntl

            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        # Another concurrent `mcp start` may have finished while we waited for the lock.
        if _mcp_tcp_listening(host, port):
            print(f"MCP HTTP already listening — {url}")
            return 0

        root = plugin_root()
        script = root / "scripts" / "llm_wiki.py"
        log_path = vault / ".mcp-sse.log"
        env = os.environ.copy()
        env["LLM_WIKI_VAULT"] = str(vault.resolve())

        cmd = [
            sys.executable,
            str(script),
            "mcp",
            "--transport",
            "sse",
            "--port",
            str(port),
            "--host",
            host,
        ]

        log_file = open(log_path, "ab", buffering=0)
        popen_kw: dict = {
            "cwd": str(root),
            "env": env,
            "stdin": subprocess.DEVNULL,
            "stdout": log_file,
            "stderr": subprocess.STDOUT,
        }
        if sys.platform == "win32":
            # Background process without a console; child keeps inherited log fd.
            popen_kw["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
                subprocess, "DETACHED_PROCESS", 0
            )
        else:
            popen_kw["start_new_session"] = True

        try:
            proc = subprocess.Popen(cmd, **popen_kw)
        except OSError as e:
            log_file.close()
            print(f"Failed to start MCP: {e}", file=sys.stderr)
            return 1

        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            if _mcp_tcp_listening(host, port):
                print(f"Started MCP HTTP in background — {url}")
                print(f"Log: {log_path}")
                return 0
            if proc.poll() is not None:
                log_file.close()
                print(
                    f"MCP server exited immediately (exit code {proc.returncode}). See {log_path}",
                    file=sys.stderr,
                )
                return 1
            time.sleep(0.15)

        print(
            f"MCP did not become ready on {host}:{port} within 15s. See {log_path}",
            file=sys.stderr,
        )
        _terminate_child_process(proc)
        log_file.close()
        return 1
    finally:
        if sys.platform == "win32":
            import msvcrt

            try:
                lock_fd.seek(0)
                msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        else:
            import fcntl

            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        lock_fd.close()


def cmd_mcp(args: argparse.Namespace) -> int:
    sub = getattr(args, "mcp_sub", None)
    if sub == "install":
        return _mcp_install(args)
    if sub == "start":
        return _mcp_start_background(args)
    vault = resolve_vault(override=getattr(args, "vault", None))
    cfg = load_config(vault)
    blocked = cli_exit_if_mcp_disabled(cfg)
    if blocked is not None:
        return blocked
    os.environ["LLM_WIKI_VAULT"] = str(vault.resolve())
    transport = getattr(args, "mcp_transport", None) or (cfg.get("mcp") or {}).get(
        "transport", "stdio"
    )
    if str(transport).lower() == "sse":
        from mcp_sse import run_sse_server

        port = getattr(args, "mcp_port", None)
        if port is None:
            port = int((cfg.get("mcp") or {}).get("port") or 8891)
        host = getattr(args, "mcp_host", None) or (cfg.get("mcp") or {}).get("host") or "127.0.0.1"
        run_sse_server(vault, port=int(port), host=str(host))
        return 0
    from mcp_server import main as mcp_main

    mcp_main()
    return 0


def _mcp_install(args: argparse.Namespace) -> int:
    """Write MCP config so Claude Code / Cursor can discover the server."""

    server_path = str((plugin_root() / "scripts" / "mcp_server.py").resolve())
    vault_arg = getattr(args, "vault", None)
    entry: dict = {"command": "python3", "args": [server_path]}
    if vault_arg:
        entry["args"].extend(["--vault", str(Path(vault_arg).resolve())])

    project = getattr(args, "project", None)
    force = getattr(args, "force", False)
    if project and not force:
        print("--project requires --force to avoid modifying an unintended Cursor project.", file=sys.stderr)
        return 2
    cursor_root = Path(project).resolve() if project else plugin_root()
    if not cursor_root.is_dir():
        print(f"Cursor project directory does not exist: {cursor_root}", file=sys.stderr)
        return 2
    cursor_cfg = cursor_root / ".cursor" / "mcp.json"
    cursor_data: dict = {}
    if cursor_cfg.exists():
        try:
            cursor_data = json.loads(cursor_cfg.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"Refusing to replace invalid Cursor MCP config {cursor_cfg}: {e}", file=sys.stderr)
            return 2
        if not isinstance(cursor_data, dict):
            print(f"Refusing to replace non-object Cursor MCP config: {cursor_cfg}", file=sys.stderr)
            return 2
        if (cursor_data.get("mcpServers") or {}).get("llm-wiki") and not force:
            print(f"{cursor_cfg} already has an llm-wiki entry; rerun with --force to replace it.", file=sys.stderr)
            return 2
    cursor_data.setdefault("mcpServers", {})["llm-wiki"] = entry
    cursor_cfg.parent.mkdir(parents=True, exist_ok=True)
    cursor_cfg.write_text(json.dumps(cursor_data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {cursor_cfg}")

    claude_cfg = Path.home() / ".claude" / "claude_desktop_config.json"
    if claude_cfg.parent.exists():
        existing = {}
        if claude_cfg.exists():
            existing = json.loads(claude_cfg.read_text(encoding="utf-8"))
        existing.setdefault("mcpServers", {})["llm-wiki"] = entry
        claude_cfg.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {claude_cfg}")
    return 0
