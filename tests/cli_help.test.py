# tests/cli_help.test.py
"""Every llm-wiki subcommand --help exits 0."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
LLM_WIKI = REPO / "scripts" / "llm_wiki.py"


def _run_help(args: list[str]) -> int:
    env = os.environ.copy()
    p = str(REPO / "scripts")
    env["PYTHONPATH"] = p + os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else p
    r = subprocess.run(
        [sys.executable, str(LLM_WIKI), *args, "--help"],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        print(r.stdout, file=sys.stderr)
    return r.returncode


def test_top_level_help():
    assert _run_help([]) == 0


@pytest.mark.parametrize(
    "sub",
    [
        "configure",
        "setup",
        "teardown",
        "build-site",
        "build-og",
        "validate",
        "ingest",
        "deps",
        "integrations",
        "git",
        "research-loop",
        "graph",
        "graph-knowledge",
        "wake-up",
        "list-topics",
        "security",
        "raw",
        "check",
        "smoke-test",
        "test-report",
    ],
)
def test_subcommand_help(sub: str):
    assert _run_help([sub]) == 0


@pytest.mark.parametrize(
    "args",
    [
        ["integrations", "status"],
        ["integrations", "validate"],
        ["git", "status"],
        ["security", "scan"],
        ["raw", "validate"],
        ["raw", "record"],
        ["raw", "finish"],
        ["raw", "rebuild-index"],
    ],
)
def test_nested_help(args: list[str]):
    assert _run_help(args) == 0
