# tests/test_hooks.py
"""Hook shell scripts: stdin JSON, env, exit 0 — complements manual QAPLAYBOOK."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
LLM_WIKI = SCRIPTS / "llm_wiki.py"


def _env_with_scripts(extra: dict[str, str]) -> dict[str, str]:
    env = dict(os.environ)
    env.update(extra)
    p = str(SCRIPTS)
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = p if not prev else f"{p}{os.pathsep}{prev}"
    return env


def _minimal_vault(tmp: Path) -> Path:
    vault = tmp / "llm-wiki"
    vault.mkdir(parents=True)
    (vault / "wiki").mkdir()
    (vault / "raw").mkdir()
    (vault / "raw" / "memory").mkdir(parents=True)
    cfg = {
        "version": 1,
        "persona": {"name": "HookTest"},
        "viewer": {"enabled": False},
        "git": {"enabled": False},
        "mcp": {"enabled": True, "search_backend": "fts5"},
        "knowledge_graph": {"enabled": True, "backend": "json"},
        "memory": {"enabled": True, "dir": "raw/memory", "max_sessions": 50},
        "integrations": {},
        "storage": {},
    }
    (vault / "config.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    (vault / "CLAUDE.md").write_text("# Rules\n", encoding="utf-8")
    (vault / "wiki" / "index.md").write_text("# Index\n", encoding="utf-8")
    (vault / "wiki" / "log.md").write_text("# Log\n", encoding="utf-8")
    return vault


@pytest.fixture
def hook_env(tmp_path: Path) -> dict[str, str]:
    if not shutil.which("jq"):
        pytest.skip("jq not on PATH (required by hooks/llm_wiki_memory.sh)")
    vault = _minimal_vault(tmp_path)
    return {
        "LLM_WIKI_VAULT": str(vault),
        "CLAUDE_PLUGIN_ROOT": str(REPO),
    }


def _run_hook(script: str, stdin: str | None, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    path = REPO / script
    assert path.is_file(), path
    return subprocess.run(
        ["bash", str(path)],
        input=stdin or "",
        text=True,
        cwd=str(REPO),
        env=_env_with_scripts(env),
        capture_output=True,
    )


def test_hook_memory_stop_writes_current_session(hook_env: dict[str, str]) -> None:
    vault = Path(hook_env["LLM_WIKI_VAULT"])
    payload = {
        "session_id": "test-abc-hook",
        "hook_event_name": "Stop",
        "last_assistant_message": "hello world",
    }
    r = _run_hook("hooks/llm_wiki_memory.sh", json.dumps(payload) + "\n", hook_env)
    assert r.returncode == 0, r.stderr + r.stdout
    assert (vault / ".current-session").read_text(encoding="utf-8").strip() == "test-abc-hook"
    memdir = vault / "raw" / "memory"
    assert any(memdir.glob("*.md")), "memory log should create or update a session file"


def test_hook_memory_post_compact_save(hook_env: dict[str, str]) -> None:
    vault = Path(hook_env["LLM_WIKI_VAULT"])
    payload = {
        "session_id": "test-def-hook",
        "hook_event_name": "PostCompact",
        "compact_summary": "Discussed auth",
    }
    r = _run_hook("hooks/llm_wiki_memory.sh", json.dumps(payload) + "\n", hook_env)
    assert r.returncode == 0, r.stderr + r.stdout
    assert any((vault / "raw" / "memory").glob("*.md"))


def test_hook_memory_session_end(hook_env: dict[str, str]) -> None:
    vault = Path(hook_env["LLM_WIKI_VAULT"])
    payload = {
        "session_id": "test-ghi-hook",
        "hook_event_name": "SessionEnd",
    }
    r = _run_hook("hooks/llm_wiki_memory.sh", json.dumps(payload) + "\n", hook_env)
    assert r.returncode == 0, r.stderr + r.stdout
    assert any((vault / "raw" / "memory").glob("*.md"))


def test_hook_precompact_exits_zero(hook_env: dict[str, str]) -> None:
    r = _run_hook("hooks/llm_wiki_precompact.sh", None, hook_env)
    assert r.returncode == 0, r.stderr + r.stdout


def test_hook_stop_exits_zero(hook_env: dict[str, str]) -> None:
    r = _run_hook("hooks/llm_wiki_stop.sh", None, hook_env)
    assert r.returncode == 0, r.stderr + r.stdout
