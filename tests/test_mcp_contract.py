# tests/test_mcp_contract.py
"""MCP server over stdio JSON-RPC (line-delimited) — transport contract."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
MCP_SERVER = SCRIPTS / "mcp_server.py"


def _minimal_vault(tmp: Path) -> Path:
    vault = tmp / "llm-wiki"
    vault.mkdir(parents=True)
    (vault / "wiki").mkdir()
    (vault / "raw").mkdir()
    (vault / "config.json").write_text(
        json.dumps(
            {
                "version": 1,
                "mcp": {"enabled": True, "search_backend": "fts5"},
                "knowledge_graph": {"enabled": True, "backend": "json"},
                "git": {"enabled": False},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (vault / "wiki" / "index.md").write_text("# Welcome\nHello.\n", encoding="utf-8")
    (vault / "wiki" / "auth.md").write_text("# Auth\nOAuth login.\n", encoding="utf-8")
    (vault / "CLAUDE.md").write_text("# X\n", encoding="utf-8")
    return vault


def _send(stdin, line: dict) -> dict:
    stdin.write(json.dumps(line) + "\n")
    stdin.flush()


def _readline(stdout) -> dict:
    raw = stdout.readline()
    if not raw:
        raise EOFError("MCP server closed stdout")
    return json.loads(raw.strip())


@pytest.fixture
def mcp_proc(tmp_path: Path):
    vault = _minimal_vault(tmp_path)
    env = dict(os.environ)
    env["LLM_WIKI_VAULT"] = str(vault)
    p = str(SCRIPTS)
    env["PYTHONPATH"] = p + os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else p
    proc = subprocess.Popen(
        [sys.executable, str(MCP_SERVER)],
        cwd=str(SCRIPTS),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        yield proc, vault
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.wait(timeout=15)


def test_mcp_stdio_tools_list_and_call(mcp_proc) -> None:
    proc, vault = mcp_proc
    assert proc.stdin and proc.stdout

    _send(proc.stdin, {"jsonrpc": "2.0", "method": "tools/list", "id": 1})
    resp = _readline(proc.stdout)
    assert resp.get("id") == 1
    assert "result" in resp
    tools = resp["result"]["tools"]
    names = {t["name"] for t in tools}
    assert "wiki_search" in names
    assert "wiki_status" in names
    assert "wiki_doctor" in names
    assert "wiki_validate" in names
    # Mutating compile tools gated by mcp.compile_enabled (default false)
    assert "wiki_lint" not in names
    assert "wiki_compile" not in names
    assert "wiki_knowledge_test" in names

    _send(
        proc.stdin,
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 2,
            "params": {"name": "wiki_search", "arguments": {"query": "OAuth", "limit": 5}},
        },
    )
    resp2 = _readline(proc.stdout)
    assert resp2.get("id") == 2
    assert "result" in resp2
    text = resp2["result"]["content"][0]["text"]
    data = json.loads(text)
    assert "results" in data or "error" in data

    _send(proc.stdin, {"jsonrpc": "2.0", "method": "tools/call", "id": 3, "params": {"name": "wiki_status", "arguments": {}}})
    resp3 = _readline(proc.stdout)
    assert resp3.get("id") == 3
    assert "result" in resp3
    t3 = json.loads(resp3["result"]["content"][0]["text"])
    assert t3.get("vault_path") == str(vault)
    assert "wiki_pages" in t3

    _send(
        proc.stdin,
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 4,
            "params": {"name": "wiki_doctor", "arguments": {}},
        },
    )
    resp4 = _readline(proc.stdout)
    doctor = json.loads(resp4["result"]["content"][0]["text"])
    assert doctor["vault_path"] == str(vault)
    assert "checks" in doctor


@pytest.mark.parametrize(
    ("client_version", "expected_version"),
    [
        ("2024-11-05", "2024-11-05"),
        ("2025-11-25", "2025-11-25"),
        ("2026-07-28", "2025-11-25"),
    ],
)
def test_mcp_initialize_negotiates_supported_protocol_version(
    mcp_proc, client_version: str, expected_version: str
) -> None:
    proc, _vault = mcp_proc
    assert proc.stdin and proc.stdout

    _send(
        proc.stdin,
        {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {"protocolVersion": client_version},
        },
    )

    assert _readline(proc.stdout)["result"]["protocolVersion"] == expected_version
