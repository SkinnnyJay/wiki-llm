# tests/test_replay_golden.py
"""Replay committed golden fixtures (CLI argv sequences) — see docs/QAPLAYBOOK.md §25."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
LLM_WIKI = REPO / "scripts" / "llm_wiki.py"
SCRIPTS = REPO / "scripts"
GOLDEN_DIR = REPO / "tests" / "fixtures" / "golden"


def _env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    if extra:
        env.update(extra)
    p = str(SCRIPTS)
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = p if not prev else f"{p}{os.pathsep}{prev}"
    return env


def _run_llm_wiki(argv: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LLM_WIKI), *argv],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )


def _setup_fresh_vault(repo_root: Path, tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    proj.mkdir()
    r = _run_llm_wiki(["setup", "--defaults", "--root", str(proj)], cwd=repo_root, env=_env())
    assert r.returncode == 0, r.stderr + r.stdout
    vault = proj / "llm-wiki"
    assert (vault / "config.json").is_file()
    return vault


def _golden_paths() -> list[Path]:
    if not GOLDEN_DIR.is_dir():
        return []
    return sorted(GOLDEN_DIR.glob("*.json"))


@pytest.mark.replay
@pytest.mark.parametrize("fixture_path", _golden_paths(), ids=lambda p: p.stem)
def test_replay_golden_fixture(fixture_path: Path, tmp_path: Path) -> None:
    vault = _setup_fresh_vault(REPO, tmp_path)
    env = _env({"LLM_WIKI_VAULT": str(vault)})

    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    steps = data.get("steps") or []

    for step in steps:
        if "argv" in step:
            argv = [str(x) for x in step["argv"]]
        elif "command" in step:
            # Legacy: single shell command string (avoid in new fixtures)
            r = subprocess.run(
                step["command"],
                shell=True,
                cwd=str(REPO),
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if step.get("expect_exit_0", True):
                assert r.returncode == 0, f"cmd failed: {step['command']}\n{r.stderr}"
            for kw in step.get("stdout_contains", []):
                if kw:
                    assert kw.lower() in (r.stdout + r.stderr).lower()
            continue
        else:
            pytest.fail(f"step must have 'argv' or 'command': {step!r}")

        r = _run_llm_wiki(argv, cwd=REPO, env=env)
        if step.get("expect_exit_0", True):
            assert r.returncode == 0, f"argv={argv!r}\n{r.stderr}\n{r.stdout}"
        out = (r.stdout or "") + (r.stderr or "")
        for kw in step.get("stdout_contains", []):
            if kw:
                assert kw.lower() in out.lower(), f"Missing {kw!r} in output for argv={argv!r}"

    for fc in data.get("file_checks", []):
        rel = fc["path"]
        p = vault / rel
        want = fc.get("exists", True)
        assert p.exists() == want, f"file check {rel}: expected exists={want}"
        if "content_contains" in fc and want:
            assert fc["content_contains"] in p.read_text(encoding="utf-8")

    if data.get("purge_vault_after", True):
        r_td = _run_llm_wiki(["teardown", "--purge", "--yes"], cwd=REPO, env=env)
        assert r_td.returncode == 0, r_td.stderr + r_td.stdout
        assert not vault.exists(), "teardown --purge should remove vault"
