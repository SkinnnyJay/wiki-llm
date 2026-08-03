"""Working examples are part of the public product contract."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MINIMAL_VAULT = REPO / "examples" / "minimal-vault"
LLM_WIKI = REPO / "scripts" / "llm_wiki.py"


def test_minimal_vault_example_uses_safe_opt_in_defaults() -> None:
    """A copyable example must not silently enable network-capable integrations."""
    cfg = json.loads((MINIMAL_VAULT / "config.json").read_text(encoding="utf-8"))

    assert (cfg["ingestion_security"] or {})["block_on_suspected"] is True
    assert all(
        integration.get("enabled") is False
        for integration in (cfg.get("integrations") or {}).values()
        if isinstance(integration, dict)
    )

    mcp = cfg.get("mcp") or {}
    assert mcp["ingest_enabled"] is False
    assert mcp["compile_enabled"] is False
    assert mcp["allow_local_file_ingest"] is False


def test_minimal_vault_example_copy_runs_documented_local_workflow(tmp_path: Path) -> None:
    """The example can be copied and validated without altering the checkout."""
    vault = tmp_path / "llm-wiki"
    shutil.copytree(MINIMAL_VAULT, vault)
    env = os.environ.copy()
    env["LLM_WIKI_VAULT"] = str(vault)
    env["PYTHONPATH"] = str(REPO / "scripts")

    for argv in (["validate", "--wikilinks"], ["lint"], ["build-site"]):
        result = subprocess.run(
            [sys.executable, str(LLM_WIKI), *argv],
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr + result.stdout

    assert (vault / "wiki" / ".og" / "wiki-data.json").is_file()
