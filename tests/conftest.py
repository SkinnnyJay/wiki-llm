"""Pytest hooks: optional network, Claude CLI, replay suites; shared fixtures."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
LLM_WIKI = REPO / "scripts" / "llm_wiki.py"
SCRIPTS = REPO / "scripts"
GOLDEN_DIR = REPO / "tests" / "fixtures" / "golden"


def _env_with_scripts(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ) if base is None else {**base}
    p = str(SCRIPTS)
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = p if not prev else f"{p}{os.pathsep}{prev}"
    return env


def pytest_runtest_setup(item: pytest.Item) -> None:
    if "network" in item.keywords:
        if os.environ.get("RUN_NETWORK_TESTS", "").lower() not in ("1", "true", "yes"):
            pytest.skip(
                "Network tests off (set RUN_NETWORK_TESTS=1 or: llm-wiki smoke-test --network)"
            )
    if "claude" in item.keywords:
        if os.environ.get("RUN_CLAUDE_TESTS", "").lower() not in ("1", "true", "yes"):
            pytest.skip(
                "Claude tests off (set RUN_CLAUDE_TESTS=1 or: llm-wiki smoke-test --claude)"
            )


@pytest.fixture(scope="session", autouse=True)
def cleanup_claude() -> Iterator[None]:
    """After the test session, prune dead Claude CLI lock files and empty session-env dirs."""
    yield
    claude_dir = Path.home() / ".claude"
    sessions = claude_dir / "sessions"
    if sessions.is_dir():
        for f in sessions.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
                pid = data.get("pid")
                if pid is not None:
                    os.kill(int(pid), 0)
            except (OSError, ProcessLookupError, ValueError, TypeError, json.JSONDecodeError):
                f.unlink(missing_ok=True)
    env_dir = claude_dir / "session-env"
    if env_dir.is_dir():
        for d in sorted(env_dir.iterdir(), reverse=True):
            if d.is_dir():
                try:
                    if not any(d.iterdir()):
                        d.rmdir()
                except OSError:
                    pass


@pytest.fixture(scope="session")
def seeded_vault(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Minimal vault with known wiki/raw content for skill evals and integration checks."""
    base = tmp_path_factory.mktemp("seeded-vault")
    vault = base / "llm-wiki"
    vault.mkdir(parents=True)
    (vault / "wiki").mkdir()
    (vault / "raw").mkdir()
    (vault / "raw" / "clips").mkdir()
    (vault / "raw" / "memory").mkdir()

    cfg: dict[str, Any] = {
        "version": 1,
        "wiki_root": "llm-wiki",
        "_meta": {"setup_completed": True, "setup_date": "2026-01-01", "setup_version": "1"},
        "persona": {"name": "EvalBot"},
        "viewer": {"enabled": True, "port": 8765, "og_base_url": "", "open_file_scheme": "file"},
        "graph": {"port": 8890, "tag_edges": True, "include_raw_nodes": True, "curated_by_edges": True},
        "integrations": {},
        "git": {"enabled": False},
        "mcp": {"enabled": True, "search_backend": "fts5"},
        "knowledge_graph": {"enabled": True, "backend": "json", "auto_update_on_ingest": False},
        "memory": {"enabled": True, "dir": "raw/memory", "max_sessions": 50},
        "benchmark": {"enabled": False},
        "metrics": {"enabled": True},
        "storage": {},
    }
    (vault / "config.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    (vault / "CLAUDE.md").write_text("# Vault rules\n", encoding="utf-8")
    (vault / "wiki" / "index.md").write_text(
        "# Index\n\n- [[auth]] — Authentication\n- [[topics/qa]] — QA topic\n",
        encoding="utf-8",
    )
    (vault / "wiki" / "log.md").write_text("# Log\n\n", encoding="utf-8")
    (vault / "wiki" / "auth.md").write_text(
        "---\ntitle: Authentication\n---\n# Auth\nWe use OAuth for login. See [[index]].\n",
        encoding="utf-8",
    )
    (vault / "wiki" / "topics").mkdir(exist_ok=True)
    (vault / "wiki" / "topics" / "qa.md").write_text(
        "# QA\n\nTest content for evals.\n", encoding="utf-8"
    )
    (vault / "raw" / "clips" / "seed.md").write_text(
        "---\ntitle: Seed clip\n---\n# Seed\nSource material for ingest tests.\n",
        encoding="utf-8",
    )
    (vault / "raw" / "memory" / "sess-eval.md").write_text(
        "---\nsession_id: sess-eval\n---\n# Session\nPrior note about authentication.\n",
        encoding="utf-8",
    )
    return vault


@pytest.fixture
def claude_runner() -> Any:
    """Run claude -p with isolation flags; skips if claude not on PATH."""

    def _run(
        *,
        prompt: str,
        vault: Path,
        budget_usd: str = "0.50",
        output_format: str = "json",
        timeout: int = 120,
        extra_args: list[str] | None = None,
        plugin_dir: Path | None = None,
        home: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        claude = shutil.which("claude")
        if not claude:
            pytest.skip("claude CLI not on PATH")
        env = _env_with_scripts()
        env["LLM_WIKI_VAULT"] = str(vault)
        if home is not None:
            env["HOME"] = str(home)
        pd = plugin_dir if plugin_dir is not None else REPO
        cmd: list[str] = [
            claude,
            "-p",
            "--bare",
            "--no-session-persistence",
            "--dangerously-skip-permissions",
            "--max-budget-usd",
            budget_usd,
            "--output-format",
            output_format,
            "--plugin-dir",
            str(pd),
        ]
        if extra_args:
            cmd.extend(extra_args)
        cmd.append(prompt)
        return subprocess.run(
            cmd,
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    return _run
