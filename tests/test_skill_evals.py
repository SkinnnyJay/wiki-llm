# tests/test_skill_evals.py
"""Agent skill smoke tests via **Claude Code** CLI (`claude -p`). Gated: ``RUN_CLAUDE_TESTS=1``.

One **named test per skill** (e.g. ``test_claude_skill_wiki_query``) so pass/fail is obvious in
``pytest -v``. Failures are appended to ``.tmp/logs/skills_evals.md`` (gitignored).

Scenarios: ``skill_eval_cases.skill_eval_cases_for_run()`` (shared with ``test_skill_evals_codex.py``).
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

import pytest

from tests.skill_eval_cases import skill_eval_cases_for_run
from tests.skill_eval_helpers import append_skill_eval_failure_log, assert_skill_eval_case


def run_claude_skill_case(
    case: dict[str, Any],
    seeded_vault,
    claude_runner,
) -> None:
    try:
        r = claude_runner(
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
        append_skill_eval_failure_log("claude", case, r, e)
        raise
    try:
        assert_skill_eval_case(case, r, seeded_vault)
    except AssertionError as e:
        append_skill_eval_failure_log("claude", case, r, e)
        raise


def _make_claude_skill_test(case: dict[str, Any]):
    skill = case["skill"]
    safe = skill.replace("-", "_")

    @pytest.mark.claude
    def test_fn(seeded_vault, claude_runner):
        run_claude_skill_case(case, seeded_vault, claude_runner)

    test_fn.__name__ = f"test_claude_skill_{safe}"
    test_fn.__doc__ = f"Claude skill smoke: {skill}."
    return test_fn


_mod = sys.modules[__name__]
for _case in skill_eval_cases_for_run():
    _t = _make_claude_skill_test(_case)
    setattr(_mod, _t.__name__, _t)
