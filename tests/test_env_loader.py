"""Tests for scripts/lib/env_loader.py."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.env_loader import _parse_env_line, load_plugin_dotenv


def test_parse_env_line():
    assert _parse_env_line("FOO=bar") == ("FOO", "bar")
    assert _parse_env_line('  KEY="x y"  ') == ("KEY", "x y")
    assert _parse_env_line("export BAZ=1") == ("BAZ", "1")
    assert _parse_env_line("# c") is None
    assert _parse_env_line("") is None


def test_load_plugin_dotenv_merge_and_respect_shell(tmp_path, monkeypatch):
    monkeypatch.delenv("ZZZ_FROM_ENV", raising=False)
    (tmp_path / ".env").write_text("ZZZ_FROM_ENV=first\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("ZZZ_FROM_ENV=second\n", encoding="utf-8")
    load_plugin_dotenv(tmp_path)
    assert os.environ.get("ZZZ_FROM_ENV") == "second"


def test_load_plugin_dotenv_shell_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("ZZZ_SHELL", "from_shell")
    (tmp_path / ".env").write_text("ZZZ_SHELL=from_file\n", encoding="utf-8")
    load_plugin_dotenv(tmp_path)
    assert os.environ.get("ZZZ_SHELL") == "from_shell"


def test_load_plugin_dotenv_empty_shell_allows_file(tmp_path, monkeypatch):
    """Empty/whitespace env placeholders must not block .env values."""
    monkeypatch.setenv("ZZZ_EMPTY", "")
    (tmp_path / ".env").write_text("ZZZ_EMPTY=from_file\n", encoding="utf-8")
    load_plugin_dotenv(tmp_path)
    assert os.environ.get("ZZZ_EMPTY") == "from_file"
