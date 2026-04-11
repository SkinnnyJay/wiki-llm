# tests/test_e2e_flow.py
"""Deterministic end-to-end CLI flow (QAPLAYBOOK section 23) — no LLM."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LLM_WIKI = REPO / "scripts" / "llm_wiki.py"
SCRIPTS = REPO / "scripts"


def _env_with_scripts(base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ) if base_env is None else {**base_env}
    p = str(SCRIPTS)
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = p if not prev else f"{p}{os.pathsep}{prev}"
    return env


def _run(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    base = _env_with_scripts(env)
    return subprocess.run(
        [sys.executable, str(LLM_WIKI), *argv],
        cwd=str(cwd),
        env=base,
        capture_output=True,
        text=True,
    )


def test_full_e2e_cli_flow(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    r = _run(["setup", "--defaults", "--root", str(proj)], cwd=REPO)
    assert r.returncode == 0, r.stderr + r.stdout

    vault = proj / "llm-wiki"
    assert (vault / "config.json").is_file()

    cfg = json.loads((vault / "config.json").read_text(encoding="utf-8"))
    cfg.setdefault("memory", {})["enabled"] = True
    (vault / "config.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

    env = {"LLM_WIKI_VAULT": str(vault)}

    r_cfg = _run(["configure", "--persona-name", "QA Bot"], cwd=REPO, env=env)
    assert r_cfg.returncode == 0, r_cfg.stderr + r_cfg.stdout
    cfg2 = json.loads((vault / "config.json").read_text(encoding="utf-8"))
    assert (cfg2.get("persona") or {}).get("name") == "QA Bot"

    r_val = _run(["validate"], cwd=REPO, env=env)
    assert r_val.returncode == 0, r_val.stderr + r_val.stdout

    qa_src = proj / "qa-note.md"
    qa_src.write_text(
        "---\ntitle: QA Test Note\nsource: manual\ndate: 2026-04-09\n---\n\n"
        "# QA Test Note\n\nTesting [[index]] and search.\n",
        encoding="utf-8",
    )

    r_ing = _run(
        ["ingest", "--tags", "qa,test", "file", str(qa_src), "--out", "clips/qa-test.md"],
        cwd=REPO,
        env=env,
    )
    assert r_ing.returncode == 0, r_ing.stderr + r_ing.stdout

    r_rv = _run(["raw", "validate", "clips/qa-test.md"], cwd=REPO, env=env)
    assert r_rv.returncode == 0, r_rv.stderr + r_rv.stdout

    r_rf = _run(
        ["raw", "finish", "clips/qa-test.md", "-m", "QA test note", "--skip-git"],
        cwd=REPO,
        env=env,
    )
    assert r_rf.returncode == 0, r_rf.stderr + r_rf.stdout

    r_bs = _run(["build-site"], cwd=REPO, env=env)
    assert r_bs.returncode == 0, r_bs.stderr + r_bs.stdout
    assert (vault / "wiki" / ".og" / "wiki-data.json").is_file()

    (vault / "wiki" / "qa-link.md").write_text("# QA link\n\n[[index]]\n", encoding="utf-8")
    r_vw = _run(["validate", "--wikilinks"], cwd=REPO, env=env)
    assert r_vw.returncode == 0, r_vw.stderr + r_vw.stdout

    r_kg1 = _run(
        ["kg", "add", "QA", "related-to", "Testing", "--source", "wiki/index.md"],
        cwd=REPO,
        env=env,
    )
    assert r_kg1.returncode == 0, r_kg1.stderr + r_kg1.stdout
    r_kg2 = _run(["kg", "query", "QA"], cwd=REPO, env=env)
    assert r_kg2.returncode == 0, r_kg2.stderr + r_kg2.stdout
    r_kg3 = _run(["kg", "stats"], cwd=REPO, env=env)
    assert r_kg3.returncode == 0, r_kg3.stderr + r_kg3.stdout

    r_ms = _run(
        [
            "memory",
            "save",
            "--session-id",
            "qa-e2e-session",
            "--summary",
            "QA e2e run",
            "--tags",
            "qa",
        ],
        cwd=REPO,
        env=env,
    )
    assert r_ms.returncode == 0, r_ms.stderr + r_ms.stdout
    r_ml = _run(["memory", "list"], cwd=REPO, env=env)
    assert r_ml.returncode == 0, r_ml.stderr + r_ml.stdout
    r_mrec = _run(["memory", "recall", "QA", "--limit", "5"], cwd=REPO, env=env)
    assert r_mrec.returncode == 0, r_mrec.stderr + r_mrec.stdout
    r_msh = _run(["memory", "show", "qa-e2e-session"], cwd=REPO, env=env)
    assert r_msh.returncode == 0, r_msh.stderr + r_msh.stdout

    out_graph = tmp_path / "graph-out"
    r_gr = _run(["graph", "--out", str(out_graph)], cwd=REPO, env=env)
    assert r_gr.returncode == 0, r_gr.stderr + r_gr.stdout
    assert (out_graph / "index.html").is_file() or list(out_graph.glob("*.html"))

    r_mst = _run(["metrics", "stats"], cwd=REPO, env=env)
    assert r_mst.returncode == 0, r_mst.stderr + r_mst.stdout

    # §23 steps 12–13: final validate + check (before teardown)
    r_fin = _run(["validate"], cwd=REPO, env=env)
    assert r_fin.returncode == 0, r_fin.stderr + r_fin.stdout
    r_ck = _run(["check"], cwd=REPO, env=env)
    assert r_ck.returncode == 0, r_ck.stderr + r_ck.stdout

    r_td = _run(["teardown", "--purge", "--yes"], cwd=REPO, env=env)
    assert r_td.returncode == 0, r_td.stderr + r_td.stdout
    assert not vault.exists(), "teardown --purge should remove vault directory"
