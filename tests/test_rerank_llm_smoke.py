"""
Opt-in integration tests for benchmark LLM rerank (API vs local CLI).

Set RUN_RERANK_SMOKE=1 to enable. API test also needs ANTHROPIC_API_KEY.
CLI test needs ``claude`` on PATH (default argv: claude -p -).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _smoke_enabled() -> bool:
    return str(os.environ.get("RUN_RERANK_SMOKE", "")).lower() in ("1", "true", "yes")


if _smoke_enabled():
    from lib.env_loader import load_plugin_dotenv
    from lib.paths import plugin_root

    load_plugin_dotenv(plugin_root())


def _tiny_vault(tmp_path: Path) -> tuple[Path, list[str], str]:
    """Two sessions; doc 2 answers 'weekly tennis' better."""
    root = tmp_path / "vault"
    raw = root / "raw" / "bench"
    raw.mkdir(parents=True)
    (raw / "s1.md").write_text(
        "---\ntitle: A\n---\n\nUser: I love tennis.\nAssistant: Great.\n",
        encoding="utf-8",
    )
    (raw / "s2.md").write_text(
        "---\ntitle: B\n---\n\nUser: My favorite sport is tennis and I play weekly.\nAssistant: Nice.\n",
        encoding="utf-8",
    )
    paths = ["raw/bench/s1.md", "raw/bench/s2.md"]
    q = "What sport does the user play weekly?"
    return root, paths, q


@pytest.mark.skipif(not _smoke_enabled(), reason="set RUN_RERANK_SMOKE=1 to run")
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
def test_rerank_anthropic_api_roundtrip(tmp_path):
    from benchmarks.bench_harness import rerank_paths_llm

    root, paths, q = _tiny_vault(tmp_path)
    out = rerank_paths_llm(
        q,
        list(paths),
        root,
        api_key=os.environ["ANTHROPIC_API_KEY"],
        invoke="anthropic_api",
        model="claude-3-5-haiku-20241022",
        max_chars=4000,
        max_candidates=10,
        excerpt_mode="head_tail",
    )
    assert len(out) == 2
    assert set(out) == set(paths)


@pytest.mark.skipif(not _smoke_enabled(), reason="set RUN_RERANK_SMOKE=1 to run")
@pytest.mark.skipif(not shutil.which("claude"), reason="claude CLI not on PATH")
def test_rerank_claude_cli_roundtrip(tmp_path):
    from benchmarks.bench_harness import rerank_paths_llm

    root, paths, q = _tiny_vault(tmp_path)
    out = rerank_paths_llm(
        q,
        list(paths),
        root,
        api_key="",
        invoke="claude_cli",
        cli_argv=["claude", "-p", "-"],
        cli_timeout_s=120,
        max_chars=4000,
        max_candidates=10,
        excerpt_mode="head_tail",
    )
    assert len(out) == 2
    assert set(out) == set(paths)
