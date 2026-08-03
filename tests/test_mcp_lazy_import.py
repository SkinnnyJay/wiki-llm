"""MCP package imports must not start or terminate a host process."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"


def test_disabled_mcp_is_importable_as_a_library(tmp_path: Path) -> None:
    vault = tmp_path / "llm-wiki"
    vault.mkdir()
    (vault / "config.json").write_text(
        json.dumps({"mcp": {"enabled": False}}), encoding="utf-8"
    )
    env = os.environ.copy()
    env["LLM_WIKI_VAULT"] = str(vault)
    env["PYTHONPATH"] = str(SCRIPTS) + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.run(
        [sys.executable, "-c", "import mcp; import mcp_server; print('imported')"],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "imported"
