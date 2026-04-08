# tests/claude.test.py
"""Optional tests that invoke the Claude Code CLI. Enable with RUN_CLAUDE_TESTS=1 or smoke-test --claude."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.mark.claude
def test_claude_plugin_validate() -> None:
    claude = shutil.which("claude")
    if not claude:
        pytest.skip("claude CLI not on PATH")
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO)
    p = str(REPO / "scripts")
    env["PYTHONPATH"] = p + os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else p
    r = subprocess.run(
        [claude, "plugin", "validate", str(REPO)],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, (r.stderr or "") + (r.stdout or "")
