# tests/test_claude_env.py
"""Unit tests for scripts/lib/claude_env.py (import via sys.path like conftest)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.claude_env import strip_anthropic_api_credentials

from tests import conftest as test_conftest


def test_strip_anthropic_api_credentials_removes_keys() -> None:
    env = {
        "PATH": "/usr/bin",
        "ANTHROPIC_API_KEY": "sk-secret",
        "ANTHROPIC_AUTH_TOKEN": "tok",
        "OTHER": "x",
    }
    out = strip_anthropic_api_credentials(env)
    assert "ANTHROPIC_API_KEY" not in out
    assert "ANTHROPIC_AUTH_TOKEN" not in out
    assert out["PATH"] == "/usr/bin"
    assert out["OTHER"] == "x"
    assert env["ANTHROPIC_API_KEY"] == "sk-secret"


def test_claude_skill_runner_uses_the_supplied_vault_as_its_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Keep agents from mistaking a plugin-root artifact for the target vault."""
    vault = tmp_path / "vault"
    vault.mkdir()
    captured: dict[str, object] = {}

    monkeypatch.setattr(test_conftest.shutil, "which", lambda _: "claude")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "ok", "")

    monkeypatch.setattr(test_conftest.subprocess, "run", fake_run)

    runner = test_conftest.claude_runner.__wrapped__()
    result = runner(prompt="read wiki/index.md", vault=vault, timeout=1)

    assert result.returncode == 0
    assert captured["cwd"] == str(vault)
