# tests/sync_agent_docs.test.py
"""Agent doc sync verification (plugin repo)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
LLM_WIKI = REPO / "scripts" / "llm_wiki.py"
sys.path.insert(0, str(SCRIPTS))


def test_verify_agent_docs_matches_shared():
    from sync_agent_docs import verify_agent_docs

    assert verify_agent_docs(REPO, quiet=True) == 0


def test_check_plugin_repo_cli_matches_qa_gate() -> None:
    """QAPLAYBOOK §0.3 — ``llm-wiki check --plugin-repo`` (agent docs + compileall)."""
    env = os.environ.copy()
    p = str(SCRIPTS)
    env["PYTHONPATH"] = p + os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else p
    r = subprocess.run(
        [sys.executable, str(LLM_WIKI), "check", "--plugin-repo"],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr + r.stdout
