"""Safety tests for the integrations settings writer."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from cli import core_commands


def test_integration_key_writer_preserves_invalid_settings_file(tmp_path: Path, monkeypatch) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text("{invalid", encoding="utf-8")
    monkeypatch.setattr(core_commands, "_claude_settings_path", lambda: settings)

    with pytest.raises(ValueError, match="invalid Claude settings JSON"):
        core_commands._set_integration_key("BRAVE_SEARCH_API_KEY", "secret")

    assert settings.read_text(encoding="utf-8") == "{invalid"


def test_integration_key_writer_preserves_existing_settings_fields(tmp_path: Path, monkeypatch) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text('{"theme":"dark","env":{"EXISTING":"keep"}}', encoding="utf-8")
    monkeypatch.setattr(core_commands, "_claude_settings_path", lambda: settings)

    core_commands._set_integration_key("BRAVE_SEARCH_API_KEY", "secret")

    assert json.loads(settings.read_text(encoding="utf-8")) == {
        "theme": "dark",
        "env": {"EXISTING": "keep", "BRAVE_SEARCH_API_KEY": "secret"},
    }
