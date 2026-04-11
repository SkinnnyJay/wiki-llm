# tests/test_claude_env.py
"""Unit tests for scripts/lib/claude_env.py (import via sys.path like conftest)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.claude_env import strip_anthropic_api_credentials


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
