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
from typing import cast

SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.config_loader import load_config
from lib.mcp_cli import cli_exit_if_mcp_disabled
from lib.paths import plugin_root, resolve_vault

# ── MCP server ───────────────────────────────────────────────────────────────

DEFAULT_MCP_HTTP_PORT = 8891
MCP_CONNECT_TIMEOUT_SECONDS = 0.35
MCP_PROCESS_TERMINATE_TIMEOUT_SECONDS = 5.0
MCP_START_TIMEOUT_SECONDS = 15.0
MCP_START_POLL_INTERVAL_SECONDS = 0.15
MCP_LOCK_RETRY_SECONDS = 0.05


def _mcp_tcp_listening(
    host: str,
    port: int,
    *,
    timeout: float = MCP_CONNECT_TIMEOUT_SECONDS,
) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _terminate_child_process(
    proc: subprocess.Popen,
    *,
    wait_s: float = MCP_PROCESS_TERMINATE_TIMEOUT_SECONDS,
) -> None:
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
        port = int(mcp_cfg.get("port") or DEFAULT_MCP_HTTP_PORT)
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
                    time.sleep(MCP_LOCK_RETRY_SECONDS)
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

        deadline = time.monotonic() + MCP_START_TIMEOUT_SECONDS
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
            time.sleep(MCP_START_POLL_INTERVAL_SECONDS)

        print(
            f"MCP did not become ready on {host}:{port} within {MCP_START_TIMEOUT_SECONDS:g}s. "
            f"See {log_path}",
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
            port = int((cfg.get("mcp") or {}).get("port") or DEFAULT_MCP_HTTP_PORT)
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
    if vault_arg is not None and not isinstance(vault_arg, (str, Path)):
        print("--vault must be a path", file=sys.stderr)
        return 2
    entry_args = [server_path]
    if vault_arg:
        entry_args.extend(["--vault", str(Path(vault_arg).resolve())])
    entry: dict[str, object] = {"command": "python3", "args": entry_args}

    project = getattr(args, "project", None)
    force = getattr(args, "force", False)
    if project is not None and not isinstance(project, (str, Path)):
        print("--project must be a path", file=sys.stderr)
        return 2
    if not isinstance(force, bool):
        print("--force must be a boolean", file=sys.stderr)
        return 2
    if project and not force:
        print("--project requires --force to avoid modifying an unintended Cursor project.", file=sys.stderr)
        return 2
    cursor_root = Path(project).resolve() if project else plugin_root()
    if not cursor_root.is_dir():
        print(f"Cursor project directory does not exist: {cursor_root}", file=sys.stderr)
        return 2
    cursor_cfg = cursor_root / ".cursor" / "mcp.json"
    cursor_data: dict[str, object] = {}
    if cursor_cfg.exists():
        try:
            cursor_data = _load_mcp_config_object(cursor_cfg)
        except ValueError as e:
            print(f"Refusing to replace invalid Cursor MCP config {cursor_cfg}: {e}", file=sys.stderr)
            return 2
        try:
            has_existing = _mcp_servers(cursor_data).get("llm-wiki") is not None
        except ValueError as e:
            print(f"Refusing to replace invalid Cursor MCP config {cursor_cfg}: {e}", file=sys.stderr)
            return 2
        if has_existing and not force:
            print(f"{cursor_cfg} already has an llm-wiki entry; rerun with --force to replace it.", file=sys.stderr)
            return 2
    try:
        _mcp_servers(cursor_data)["llm-wiki"] = entry
    except ValueError as e:
        print(f"Refusing to replace invalid Cursor MCP config {cursor_cfg}: {e}", file=sys.stderr)
        return 2
    cursor_cfg.parent.mkdir(parents=True, exist_ok=True)
    cursor_cfg.write_text(json.dumps(cursor_data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {cursor_cfg}")

    claude_cfg = Path.home() / ".claude" / "claude_desktop_config.json"
    if claude_cfg.parent.exists():
        existing: dict[str, object] = {}
        if claude_cfg.exists():
            try:
                existing = _load_mcp_config_object(claude_cfg)
            except ValueError as e:
                print(f"Refusing to replace invalid Claude MCP config {claude_cfg}: {e}", file=sys.stderr)
                return 2
        try:
            _mcp_servers(existing)["llm-wiki"] = entry
        except ValueError as e:
            print(f"Refusing to replace invalid Claude MCP config {claude_cfg}: {e}", file=sys.stderr)
            return 2
        claude_cfg.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {claude_cfg}")
    return 0


def _load_mcp_config_object(path: Path) -> dict[str, object]:
    """Decode a user-owned MCP config without permitting malformed root shapes."""
    try:
        decoded = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(str(exc)) from exc
    if not isinstance(decoded, dict):
        raise ValueError("JSON root must be an object")
    return cast(dict[str, object], decoded)


def _mcp_servers(config: dict[str, object]) -> dict[str, object]:
    """Return a writable MCP server map, rejecting a conflicting user shape."""
    current = config.get("mcpServers")
    if current is None:
        servers: dict[str, object] = {}
        config["mcpServers"] = servers
        return servers
    if not isinstance(current, dict):
        raise ValueError("mcpServers must be an object")
    return cast(dict[str, object], current)
