# tests/test_skill_evals.py
"""Agent-driven skill smoke evals (claude -p). Gated: RUN_CLAUDE_TESTS=1."""

from __future__ import annotations

import pytest

SKILL_EVALS = [
    {
        "skill": "wiki-query",
        "prompt": (
            "You are in the llm-wiki vault. Answer in 2 sentences: what do we know about "
            "authentication or OAuth? You must cite at least one path under wiki/ (e.g. wiki/auth.md)."
        ),
        "budget_usd": "0.50",
        "timeout": 120,
        "check_output": ["wiki/"],
    },
    {
        "skill": "wiki-status",
        "prompt": (
            "Run shell from repo: llm-wiki validate  (vault is LLM_WIKI_VAULT). "
            "Reply with one word: OK or FAIL plus one line of stderr if any."
        ),
        "budget_usd": "0.35",
        "timeout": 90,
        "check_output": ["ok"],
    },
    {
        "skill": "wiki-session-memory",
        "prompt": (
            "Run: llm-wiki memory list   from the vault. Reply with the first line of output only."
        ),
        "budget_usd": "0.25",
        "timeout": 60,
        "check_output": [],
    },
]


@pytest.mark.claude
@pytest.mark.parametrize("case", SKILL_EVALS, ids=lambda c: c["skill"])
def test_skill_eval_smoke(case, seeded_vault, claude_runner):
    """Loose keyword checks on stdout — review failures as model drift, not hard bugs."""
    r = claude_runner(
        prompt=case["prompt"],
        vault=seeded_vault,
        budget_usd=case["budget_usd"],
        timeout=case["timeout"],
        output_format="text",
    )
    assert r.returncode == 0, r.stderr + r.stdout
    out = (r.stdout or "") + (r.stderr or "")
    for kw in case.get("check_output", []):
        if not kw:
            continue
        assert kw.lower() in out.lower(), f"expected {kw!r} in output for {case['skill']}"
    for path, should_exist in case.get("check_files", []):
        assert (seeded_vault / path).exists() == should_exist
