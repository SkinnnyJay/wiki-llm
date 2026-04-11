# tests/test_skill_evals_codex.py
"""Optional **Codex** CLI mirror of skill evals (same cases as ``test_skill_evals.py``).

Opt-in: ``RUN_CODEX_SKILL_EVALS=1`` (in addition to tooling on PATH). Revisit when we
want first-class Codex coverage; Claude remains the default path.

Why Codex differs from Claude Code for plugins/skills/workflows:
https://blog.fsck.com/2025/10/27/skills-for-openai-codex/
"""

from __future__ import annotations

import pytest

from tests.skill_eval_cases import SKILL_EVALS


@pytest.mark.codex_skill_eval
@pytest.mark.parametrize("case", SKILL_EVALS, ids=lambda c: c["skill"])
def test_skill_eval_smoke_codex(case, seeded_vault, codex_runner):
    """Same scenarios as ``test_skill_eval_smoke``, via ``codex exec``."""
    r = codex_runner(
        prompt=case["prompt"],
        vault=seeded_vault,
        budget_usd=case.get("budget_usd"),
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
