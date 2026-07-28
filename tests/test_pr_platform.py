"""Focused regression tests for CLI platform conveniences."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cli.core_commands import cmd_search, cmd_teardown
from lib.config_loader import DEFAULTS, merge_missing_defaults


def test_config_migration_adds_missing_keys_without_replacing_values() -> None:
    config = {"mcp": {"search_backend": "grep"}}

    added = merge_missing_defaults(config)

    assert "ingestion.max_download_bytes" in added
    assert config["mcp"]["search_backend"] == "grep"
    assert config["ingestion"]["max_download_bytes"] == DEFAULTS["ingestion"]["max_download_bytes"]


def test_teardown_artifacts_preserves_vault_content(tmp_path: Path) -> None:
    vault = tmp_path / "llm-wiki"
    page = vault / "wiki" / "page.md"
    page.parent.mkdir(parents=True)
    page.write_text("# Kept\n", encoding="utf-8")
    raw = vault / "raw"
    raw.mkdir()
    (vault / ".kg.json").write_text("{}", encoding="utf-8")
    (vault / ".search.sqlite3").write_text("", encoding="utf-8")
    (raw / ".hashes.json").write_text("{}", encoding="utf-8")
    (raw / ".tags.json").write_text("{}", encoding="utf-8")

    args = type("Args", (), {"vault": str(vault), "artifacts": True, "yes": True, "dry_run": False, "purge": False})()
    assert cmd_teardown(args) == 0

    assert page.read_text(encoding="utf-8") == "# Kept\n"
    assert not (vault / ".kg.json").exists()
    assert not (vault / ".search.sqlite3").exists()
    assert not (raw / ".hashes.json").exists()
    assert not (raw / ".tags.json").exists()


def test_search_cli_uses_configured_backend_and_scope(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "llm-wiki"
    (vault / "wiki").mkdir(parents=True)
    (vault / "raw").mkdir()
    (vault / "config.json").write_text(
        json.dumps({"mcp": {"search_backend": "grep"}}),
        encoding="utf-8",
    )
    (vault / "wiki" / "match.md").write_text("# Match\nneedle\n", encoding="utf-8")
    (vault / "raw" / "ignored.md").write_text("# Ignored\nneedle\n", encoding="utf-8")

    args = type(
        "Args",
        (),
        {"vault": str(vault), "query": "needle", "limit": 5, "tag": "", "scope": "wiki"},
    )()
    assert cmd_search(args) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["backend"] == "grep"
    assert [item["path"] for item in result["results"]] == ["wiki/match.md"]


def test_url_ingest_uses_configured_download_cap(tmp_path: Path, monkeypatch) -> None:
    from ingest.adapters.url import UrlAdapter

    vault = tmp_path / "llm-wiki"
    (vault / "raw").mkdir(parents=True)
    captured: dict[str, int] = {}

    def fake_fetch(_url: str, **kwargs):
        captured["max_bytes"] = kwargs["max_bytes"]
        return b"body", "https://example.com/page", "text/plain"

    monkeypatch.setattr("ingest.adapters.url.safe_fetch", fake_fetch)
    UrlAdapter().run(
        vault,
        {"ingestion": {"max_download_bytes": 1234}},
        ["https://example.com/page"],
    )

    assert captured["max_bytes"] == 1234


def test_windows_wrapper_forwards_to_cli_script() -> None:
    wrapper = (REPO / "bin" / "llm-wiki.cmd").read_text(encoding="utf-8")

    assert r"scripts\llm_wiki.py" in wrapper
    assert "%*" in wrapper
