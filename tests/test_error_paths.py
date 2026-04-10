# tests/test_error_paths.py
"""Error-path coverage: config, empty dirs, broken wikilinks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
LLM_WIKI = REPO / "scripts" / "llm_wiki.py"


def _run(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    base = os.environ.copy()
    p = str(REPO / "scripts")
    base["PYTHONPATH"] = p + os.pathsep + base.get("PYTHONPATH", "") if base.get("PYTHONPATH") else p
    if env:
        base.update(env)
    return subprocess.run(
        [sys.executable, str(LLM_WIKI), *argv],
        cwd=str(cwd),
        env=base,
        capture_output=True,
        text=True,
    )


def test_missing_config_json_uses_defaults(tmp_path: Path) -> None:
    sys.path.insert(0, str(REPO / "scripts"))
    from lib.config_loader import DEFAULTS, load_config

    vault = tmp_path / "v"
    vault.mkdir()
    cfg = load_config(vault)
    assert cfg["version"] == DEFAULTS["version"]


def test_corrupt_config_json_raises(tmp_path: Path) -> None:
    sys.path.insert(0, str(REPO / "scripts"))
    from lib.config_loader import load_config

    vault = tmp_path / "v"
    vault.mkdir()
    (vault / "config.json").write_text("{invalid json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_config(vault)


def test_build_site_empty_wiki_succeeds(tmp_path: Path) -> None:
    """wiki/ exists but has no .md files — build-site should not crash."""
    proj = tmp_path / "proj"
    proj.mkdir()
    r = _run(["setup", "--root", str(proj)], cwd=REPO)
    assert r.returncode == 0, r.stderr + r.stdout

    vault = proj / "llm-wiki"
    wiki = vault / "wiki"
    for p in wiki.rglob("*.md"):
        if ".og" not in p.parts:
            p.unlink()

    env = {"LLM_WIKI_VAULT": str(vault)}
    r2 = _run(["build-site"], cwd=REPO, env=env)
    assert r2.returncode == 0, r2.stderr + r2.stdout
    assert (wiki / ".og" / "wiki-data.json").is_file()


def test_ingest_unknown_adapter_exits_nonzero(tmp_path: Path) -> None:
    """ingest with an unknown adapter name exits non-zero without a traceback."""
    proj = tmp_path / "proj"
    proj.mkdir()
    r = _run(["setup", "--root", str(proj)], cwd=REPO)
    assert r.returncode == 0, r.stderr + r.stdout

    vault = proj / "llm-wiki"
    env = {"LLM_WIKI_VAULT": str(vault)}
    r2 = _run(["ingest", "not_a_real_adapter_xyz", "--out", "x.md"], cwd=REPO, env=env)
    assert r2.returncode != 0


def test_raw_validate_missing_file_exits_nonzero(tmp_path: Path) -> None:
    """`raw validate` requires a path; missing file under raw/ exits 1 without a traceback."""
    proj = tmp_path / "proj"
    proj.mkdir()
    r = _run(["setup", "--root", str(proj)], cwd=REPO)
    assert r.returncode == 0, r.stderr + r.stdout

    vault = proj / "llm-wiki"
    env = {"LLM_WIKI_VAULT": str(vault)}
    r2 = _run(["raw", "validate", "does-not-exist.md"], cwd=REPO, env=env)
    assert r2.returncode != 0


def test_validate_corrupt_config_exits_nonzero(tmp_path: Path) -> None:
    """validate must exit 1 with a clear message when config.json is not valid JSON."""
    proj = tmp_path / "proj"
    proj.mkdir()
    r = _run(["setup", "--root", str(proj)], cwd=REPO)
    assert r.returncode == 0, r.stderr + r.stdout

    vault = proj / "llm-wiki"
    (vault / "config.json").write_text("{not json", encoding="utf-8")
    env = {"LLM_WIKI_VAULT": str(vault)}
    r2 = _run(["validate"], cwd=REPO, env=env)
    assert r2.returncode != 0
    assert "Invalid config.json" in (r2.stderr + r2.stdout) or "Invalid config" in (r2.stderr + r2.stdout)


def test_validate_wikilinks_broken_link_exits_nonzero(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    r = _run(["setup", "--root", str(proj)], cwd=REPO)
    assert r.returncode == 0, r.stderr + r.stdout

    vault = proj / "llm-wiki"
    # Link to a page that does not exist
    (vault / "wiki" / "broken.md").write_text("# Broken\n\n[[missing-page]]\n", encoding="utf-8")

    env = {"LLM_WIKI_VAULT": str(vault)}
    r2 = _run(["validate", "--wikilinks"], cwd=REPO, env=env)
    assert r2.returncode != 0, r2.stdout + r2.stderr
    assert "broken wikilink" in (r2.stderr + r2.stdout).lower()
