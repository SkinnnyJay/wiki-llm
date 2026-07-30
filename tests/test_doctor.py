"""Tests for deterministic vault diagnostics and safe repairs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.doctor import doctor_report


def test_doctor_reports_missing_vault(tmp_path: Path) -> None:
    report = doctor_report(tmp_path / "missing")

    assert report["ok"] is False
    assert any(check["name"] == "vault" and check["status"] == "error" for check in report["checks"])


def test_doctor_fix_creates_dirs_and_restores_safe_blank_defaults(tmp_path: Path) -> None:
    vault = tmp_path / "llm-wiki"
    vault.mkdir()
    (vault / "config.json").write_text(
        json.dumps({"mcp": {"enabled": "", "search_backend": ""}, "persona": {"name": ""}}),
        encoding="utf-8",
    )

    report = doctor_report(vault, fix=True)
    saved = json.loads((vault / "config.json").read_text(encoding="utf-8"))

    assert report["ok"] is True
    assert (vault / "raw").is_dir()
    assert (vault / "wiki").is_dir()
    assert saved["mcp"]["enabled"] is True
    assert saved["mcp"]["search_backend"] == "fts5"
    assert saved["persona"]["name"] == "Gennie"
    assert saved["ingestion"]["max_download_bytes"] == 32 * 1024 * 1024


def test_doctor_warns_about_quarantined_indexes(tmp_path: Path) -> None:
    vault = tmp_path / "llm-wiki"
    (vault / "raw").mkdir(parents=True)
    (vault / "wiki").mkdir()
    (vault / "config.json").write_text("{}", encoding="utf-8")
    (vault / "raw" / ".tags.json.corrupt.20260728T000000Z").write_text("bad", encoding="utf-8")

    report = doctor_report(vault)
    check = next(check for check in report["checks"] if check["name"] == "corrupt_indexes")

    assert check["status"] == "warn"
    assert check["files"] == ["raw/.tags.json.corrupt.20260728T000000Z"]


def test_doctor_includes_compile_health(tmp_path: Path) -> None:
    vault = tmp_path / "llm-wiki"
    (vault / "raw").mkdir(parents=True)
    (vault / "wiki").mkdir()
    (vault / "config.json").write_text(
        json.dumps(
            {
                "version": 1,
                "mcp": {"enabled": True, "search_backend": "fts5"},
                "knowledge_graph": {"enabled": True, "backend": "json"},
                "compile": {"extract_claims": True},
                "viewer": {"enabled": False},
                "git": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )
    (vault / "wiki" / "index.md").write_text("# Index\n\n[[topic]]\n", encoding="utf-8")
    (vault / "wiki" / "topic.md").write_text("# Topic\n", encoding="utf-8")
    (vault / "CLAUDE.md").write_text("# v\n", encoding="utf-8")

    report = doctor_report(vault)
    names = {c["name"] for c in report["checks"]}
    assert "compile.config" in names
    assert "lint" in names
    assert "claims" in names
    assert "kg.conflicts" in names
    # Doctor must not mutate claims index
    assert not (vault / "outputs" / "claims.json").exists()
