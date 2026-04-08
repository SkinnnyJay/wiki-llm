# tests/vault_flow.test.py
"""Deterministic vault: setup → ingest file → raw validate → build-site → validate → graph."""

from __future__ import annotations

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


def test_vault_ingest_build_graph(tmp_path: Path):
    proj = tmp_path / "proj"
    proj.mkdir()
    r = _run(["setup", "--root", str(proj)], cwd=REPO)
    assert r.returncode == 0, r.stderr + r.stdout

    vault = proj / "llm-wiki"
    assert (vault / "config.json").is_file()

    sample = proj / "note.md"
    sample.write_text("# Smoke test note\n\nHello.\n", encoding="utf-8")

    env = {"LLM_WIKI_VAULT": str(vault)}
    r2 = _run(
        ["ingest", "file", str(sample), "--out", "smoke-note.md"],
        cwd=REPO,
        env=env,
    )
    assert r2.returncode == 0, r2.stderr + r2.stdout

    raw_md = vault / "raw" / "smoke-note.md"
    assert raw_md.is_file()

    r3 = _run(["raw", "validate", "smoke-note.md"], cwd=REPO, env=env)
    assert r3.returncode == 0, r3.stderr + r3.stdout

    (vault / "wiki" / "smoke.md").write_text("# Smoke\n\n[[index]]\n", encoding="utf-8")

    r4 = _run(["build-site"], cwd=REPO, env=env)
    assert r4.returncode == 0, r4.stderr + r4.stdout

    r5 = _run(["validate", "--wikilinks"], cwd=REPO, env=env)
    assert r5.returncode == 0, r5.stderr + r5.stdout

    out_graph = tmp_path / "graph-out"
    r6 = _run(["graph", "--out", str(out_graph)], cwd=REPO, env=env)
    assert r6.returncode == 0, r6.stderr + r6.stdout
    assert (out_graph / "index.html").is_file() or list(out_graph.glob("*.html"))
