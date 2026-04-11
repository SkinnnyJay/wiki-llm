"""Pytest hooks: optional network, Claude CLI, replay suites; shared fixtures."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from lib.claude_env import strip_anthropic_api_credentials

LLM_WIKI = REPO / "scripts" / "llm_wiki.py"
GOLDEN_DIR = REPO / "tests" / "fixtures" / "golden"


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def pytest_sessionstart(session: pytest.Session) -> None:
    """One-time stderr notice when expensive / external tiers are enabled."""
    lines: list[str] = []
    if _truthy_env("RUN_NETWORK_TESTS"):
        lines.append(
            "llm-wiki pytest: RUN_NETWORK_TESTS=1 — external HTTPS/network may be used."
        )
    if _truthy_env("RUN_CLAUDE_TESTS"):
        lines.append(
            "llm-wiki pytest: RUN_CLAUDE_TESTS=1 — Claude CLI; subscription or API usage may apply."
        )
    if _truthy_env("RUN_CODEX_SKILL_EVALS"):
        lines.append(
            "llm-wiki pytest: RUN_CODEX_SKILL_EVALS=1 — Codex CLI; API usage may apply."
        )
    if _truthy_env("RUN_BROWSER_TESTS"):
        lines.append(
            "llm-wiki pytest: RUN_BROWSER_TESTS=1 — Playwright (local browser; not an LLM)."
        )
    if _truthy_env("RUN_MINIMAL_SKILL_EVALS"):
        lines.append(
            "llm-wiki pytest: RUN_MINIMAL_SKILL_EVALS=1 — only core wiki-query/wiki-status/wiki-session-memory skill evals."
        )
    if lines:
        print("---", file=sys.stderr)
        for line in lines:
            print(line, file=sys.stderr)
        print("---", file=sys.stderr)


def _env_with_scripts(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ) if base is None else {**base}
    p = str(SCRIPTS)
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = p if not prev else f"{p}{os.pathsep}{prev}"
    return env


def _env_for_skill_eval(vault: Path) -> dict[str, str]:
    """Env for agent skill smoke tests: vault + repo ``bin/`` on PATH (``llm-wiki``)."""
    env = _env_with_scripts()
    env["LLM_WIKI_VAULT"] = str(vault)
    bin_dir = str(REPO / "bin")
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
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
    if "codex_skill_eval" in item.keywords:
        if os.environ.get("RUN_CODEX_SKILL_EVALS", "").lower() not in ("1", "true", "yes"):
            pytest.skip(
                "Codex skill evals off (set RUN_CODEX_SKILL_EVALS=1)"
            )
    if "browser" in item.keywords:
        if os.environ.get("RUN_BROWSER_TESTS", "").lower() not in ("1", "true", "yes"):
            pytest.skip(
                "Browser tests off (set RUN_BROWSER_TESTS=1 or: llm-wiki smoke-test --browser)"
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
    """Run ``claude -p`` with isolation flags; skips if claude not on PATH.

    **No ``--bare`` by default:** ``--bare`` restricts Anthropic auth to
    ``ANTHROPIC_API_KEY`` / ``apiKeyHelper`` and disables OAuth and keychain
    (see ``claude --help``). That forces API-credit billing and breaks the
    usual Claude Code subscription flow. Pass ``bare=True`` only for
    API-key-only sandboxes.

    **``budget_usd``:** pass ``None`` to omit ``--max-budget-usd``. The CLI
    documents that flag as capping spend on **API** calls; it can interact
    badly with Claude Code subscription billing (same symptom as API credits).

    **Env parity with Codex skill evals:** uses ``_env_for_skill_eval`` (``LLM_WIKI_VAULT``
    + repo ``bin/`` on ``PATH``) so ``llm-wiki`` resolves like ``codex_runner``.

    **API keys:** we **strip** ``ANTHROPIC_*`` from the subprocess env (unless ``bare=True`` or
    ``CLAUDE_RUNNER_KEEP_ANTHROPIC_ENV=1``).

    **Vault visibility:** passes ``--add-dir`` with the vault path and ``--`` before the
    prompt (``--add-dir`` otherwise consumes the prompt as another directory).

    **Settings sources:** default ``--setting-sources=project`` so we do **not** merge
    ``~/.claude/settings.json`` (its ``env`` block often injects ``ANTHROPIC_API_KEY``,
    which forces **API credits** and yields “Credit balance is too low” even when
    **Claude Max** works in TTY — subscription auth lives in keychain/OAuth, not that file).
    Project scope still picks up repo ``.claude/`` (rules) while skipping gitignored
    ``settings.local.json`` unless you add ``local``. Use
    ``CLAUDE_RUNNER_SETTING_SOURCES=user,project,local`` for the same merges as interactive.
    """

    def _run(
        *,
        prompt: str,
        vault: Path,
        budget_usd: str | None = None,
        output_format: str = "json",
        timeout: int = 120,
        extra_args: list[str] | None = None,
        plugin_dir: Path | None = None,
        home: Path | None = None,
        bare: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        claude = shutil.which("claude")
        if not claude:
            pytest.skip("claude CLI not on PATH")
        env = _env_for_skill_eval(vault)
        if home is not None:
            env["HOME"] = str(home)
        if not bare and os.environ.get("CLAUDE_RUNNER_KEEP_ANTHROPIC_ENV", "").lower() not in (
            "1",
            "true",
            "yes",
        ):
            env = strip_anthropic_api_credentials(env)
        pd = plugin_dir if plugin_dir is not None else REPO
        cmd: list[str] = [claude, "-p"]
        if bare:
            cmd.append("--bare")
        else:
            # Default ``project`` only: do not merge ``~/.claude/settings.json`` (often has
            # env.ANTHROPIC_API_KEY → API billing) or ``local`` (repo settings.local.json keys).
            # Override: ``CLAUDE_RUNNER_SETTING_SOURCES=user,project,local``.
            ss = os.environ.get("CLAUDE_RUNNER_SETTING_SOURCES", "project").strip()
            if ss:
                cmd.extend(["--setting-sources", ss])
        cmd.extend(
            [
                "--no-session-persistence",
                "--dangerously-skip-permissions",
            ]
        )
        if budget_usd is not None:
            cmd.extend(["--max-budget-usd", budget_usd])
        cmd.extend(
            [
                "--output-format",
                output_format,
                "--plugin-dir",
                str(pd),
                "--add-dir",
                str(vault),
            ]
        )
        if extra_args:
            cmd.extend(extra_args)
        # ``--add-dir`` accepts multiple paths; ``--`` stops option parsing so ``prompt`` is not a dir.
        cmd.extend(["--", prompt])
        return subprocess.run(
            cmd,
            cwd=str(REPO),
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    return _run


@pytest.fixture
def codex_runner() -> Any:
    """Run ``codex exec`` non-interactively for skill evals; skips if ``codex`` not on PATH."""

    def _run(
        *,
        prompt: str,
        vault: Path,
        budget_usd: str | None = None,
        output_format: str = "text",
        timeout: int = 120,
        extra_args: list[str] | None = None,
        plugin_dir: Path | None = None,
        home: Path | None = None,
        bare: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        _ = (budget_usd, output_format, plugin_dir, bare)  # Claude-only; kept for call compatibility
        codex = shutil.which("codex")
        if not codex:
            pytest.skip("codex CLI not on PATH")
        env = _env_for_skill_eval(vault)
        if home is not None:
            env["HOME"] = str(home)
        cmd: list[str] = [
            codex,
            "exec",
            "-s",
            "workspace-write",
            "--skip-git-repo-check",
            "-C",
            str(REPO),
        ]
        if extra_args:
            cmd.extend(extra_args)
        cmd.append(prompt)
        return subprocess.run(
            cmd,
            cwd=str(REPO),
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    return _run


@pytest.fixture
def skill_eval_runner(request: Any) -> Any:
    """Dispatch skill eval subprocess: ``SKILL_EVAL_BACKEND=claude`` (default) or ``codex``."""

    backend = os.environ.get("SKILL_EVAL_BACKEND", "claude").strip().lower() or "claude"
    if backend == "codex":
        return request.getfixturevalue("codex_runner")
    if backend == "claude":
        return request.getfixturevalue("claude_runner")
    pytest.skip(f"Unknown SKILL_EVAL_BACKEND={backend!r} (use codex or claude)")
