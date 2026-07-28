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


def test_version():
    r = subprocess.run(
        [str(REPO / "bin" / "llm-wiki"), "--version"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "0.2.0"


def test_setup_accepts_vault_after_subcommand():
    """`--vault` on the parent must come before setup; setup also accepts --vault after setup."""
    env = os.environ.copy()
    p = str(REPO / "scripts")
    env["PYTHONPATH"] = p + os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else p
    r = subprocess.run(
        [sys.executable, str(LLM_WIKI), "setup", "--help"],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert "--vault" in r.stdout


def test_no_subcommand_prints_help_exit_zero():
    """Bare `llm-wiki` (no cmd) must not error — plugin adds bin/ to PATH; probes use no args."""
    env = os.environ.copy()
    p = str(REPO / "scripts")
    env["PYTHONPATH"] = p + os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else p
    r = subprocess.run(
        [sys.executable, str(LLM_WIKI)],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "usage:" in (r.stdout + r.stderr).lower()


@pytest.mark.parametrize(
    "sub",
    [
        "configure",
        "setup",
        "teardown",
        "build-site",
        "build-og",
        "validate",
        "doctor",
        "search",
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
        "sync-agent-docs",
        "smoke-test",
        "test-report",
        "mcp",
        "kg",
        "metrics",
        "benchmark",
        "memory",
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
        ["mcp", "install"],
        ["mcp", "start"],
        ["kg", "add"],
        ["kg", "query"],
        ["kg", "invalidate"],
        ["kg", "timeline"],
        ["kg", "stats"],
        ["kg", "rebuild"],
        ["metrics", "record"],
        ["metrics", "query"],
        ["metrics", "stats"],
        ["metrics", "clear"],
        ["metrics", "report"],
        ["metrics", "summary"],
        ["benchmark", "run"],
        ["benchmark", "report"],
        ["benchmark", "history"],
        ["benchmark", "compare"],
        ["benchmark", "analyze"],
        ["benchmark", "suites"],
        ["memory", "save"],
        ["memory", "log"],
        ["memory", "list"],
        ["memory", "show"],
        ["memory", "recall"],
        ["memory", "prune"],
    ],
)
def test_nested_help(args: list[str]):
    assert _run_help(args) == 0
