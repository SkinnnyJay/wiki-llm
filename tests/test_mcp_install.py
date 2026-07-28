"""Tests for safe MCP editor registration paths."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from cli import mcp_commands  # noqa: E402


def test_mcp_install_writes_plugin_cursor_config_and_preserves_servers(
    tmp_path: Path, monkeypatch
) -> None:
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    monkeypatch.setattr(mcp_commands, "plugin_root", lambda: plugin)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    assert mcp_commands._mcp_install(argparse.Namespace(vault=None, project=None, force=False)) == 0

    cursor_config = plugin / ".cursor" / "mcp.json"
    config = json.loads(cursor_config.read_text(encoding="utf-8"))
    assert config["mcpServers"]["llm-wiki"]["args"] == [str(plugin / "scripts" / "mcp_server.py")]
    config["mcpServers"]["other"] = {"command": "other"}
    cursor_config.write_text(json.dumps(config), encoding="utf-8")

    assert mcp_commands._mcp_install(argparse.Namespace(vault=None, project=None, force=True)) == 0
    updated = json.loads(cursor_config.read_text(encoding="utf-8"))
    assert updated["mcpServers"]["other"] == {"command": "other"}


def test_mcp_install_requires_force_for_explicit_project(tmp_path: Path, monkeypatch) -> None:
    plugin = tmp_path / "plugin"
    project = tmp_path / "project"
    plugin.mkdir()
    project.mkdir()
    monkeypatch.setattr(mcp_commands, "plugin_root", lambda: plugin)

    args = argparse.Namespace(vault=None, project=project, force=False)
    assert mcp_commands._mcp_install(args) == 2
    assert not (project / ".cursor" / "mcp.json").exists()
