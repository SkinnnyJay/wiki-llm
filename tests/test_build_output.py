# tests/test_build_output.py
"""Assert build-site and graph emit expected JSON/HTML structure."""

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


def _assert_graph_json(data: dict) -> None:
    assert "nodes" in data and "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)
    for n in data["nodes"]:
        assert "id" in n and "title" in n
    for e in data["edges"]:
        assert "source" in e and "target" in e


@pytest.fixture
def minimal_vault(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    proj.mkdir()
    r = _run(["setup", "--root", str(proj)], cwd=REPO)
    assert r.returncode == 0, r.stderr + r.stdout
    vault = proj / "llm-wiki"
    (vault / "wiki" / "smoke.md").write_text("# Smoke\n\n[[index]]\n", encoding="utf-8")
    return vault


def test_build_site_output_structure(minimal_vault: Path) -> None:
    env = {"LLM_WIKI_VAULT": str(minimal_vault)}
    r = _run(["build-site"], cwd=REPO, env=env)
    assert r.returncode == 0, r.stderr + r.stdout

    og = minimal_vault / "wiki" / ".og"
    assert (og / "index.html").is_file()
    data_path = og / "wiki-data.json"
    assert data_path.is_file()
    data = json.loads(data_path.read_text(encoding="utf-8"))
    assert "nodes" in data and "edges" in data
    _assert_graph_json(data)


def test_graph_output_structure(minimal_vault: Path, tmp_path: Path) -> None:
    env = {"LLM_WIKI_VAULT": str(minimal_vault)}
    r1 = _run(["build-site"], cwd=REPO, env=env)
    assert r1.returncode == 0, r1.stderr + r1.stdout

    out_graph = tmp_path / "graph-out"
    r2 = _run(["graph", "--out", str(out_graph)], cwd=REPO, env=env)
    assert r2.returncode == 0, r2.stderr + r2.stdout

    assert (out_graph / "index.html").is_file()
    gpath = out_graph / "graph-data.json"
    assert gpath.is_file()
    gdata = json.loads(gpath.read_text(encoding="utf-8"))
    _assert_graph_json(gdata)
