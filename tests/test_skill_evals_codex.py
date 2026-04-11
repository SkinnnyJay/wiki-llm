# tests/test_skill_evals_codex.py
"""Optional **Codex** CLI mirror — one named test per skill; failures logged to
``.tmp/logs/skills_evals.md``.

Opt-in: ``RUN_CODEX_SKILL_EVALS=1`` (in addition to tooling on PATH).

Why Codex differs from Claude Code for plugins/skills/workflows:
https://blog.fsck.com/2025/10/27/skills-for-openai-codex/
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

import pytest

from tests.skill_eval_cases import skill_eval_cases_for_run
from tests.skill_eval_helpers import append_skill_eval_failure_log, assert_skill_eval_case


def run_codex_skill_case(
    case: dict[str, Any],
    seeded_vault,
    codex_runner,
) -> None:
    try:
        r = codex_runner(
            prompt=case["prompt"],
            vault=seeded_vault,
            budget_usd=case.get("budget_usd"),
            timeout=case["timeout"],
            output_format="text",
        )
    except Exception as e:
        r = subprocess.CompletedProcess(
            [],
            returncode=-1,
            stdout="",
            stderr=f"{type(e).__name__}: {e}",
        )
        append_skill_eval_failure_log("codex", case, r, e)
        raise
    try:
        assert_skill_eval_case(case, r, seeded_vault)
    except AssertionError as e:
        append_skill_eval_failure_log("codex", case, r, e)
        raise


def _make_codex_skill_test(case: dict[str, Any]):
    skill = case["skill"]
    safe = skill.replace("-", "_")

    @pytest.mark.codex_skill_eval
    def test_fn(seeded_vault, codex_runner):
        run_codex_skill_case(case, seeded_vault, codex_runner)

    test_fn.__name__ = f"test_codex_skill_{safe}"
    test_fn.__doc__ = f"Codex skill smoke: {skill}."
    return test_fn


_mod = sys.modules[__name__]
for _case in skill_eval_cases_for_run():
    _t = _make_codex_skill_test(_case)
    setattr(_mod, _t.__name__, _t)
