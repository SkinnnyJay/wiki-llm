"""Deterministic inventory: wiki skills partition (eval vs excluded), commands/skills glob."""

from __future__ import annotations

from pathlib import Path

from tests.skill_eval_cases import SKILL_EVALS, SKILL_EVAL_EXCLUDE

REPO = Path(__file__).resolve().parent.parent


def test_wiki_skill_dirs_match_eval_cases_or_exclusions() -> None:
    """Every ``skills/wiki-*/SKILL.md`` is either in ``SKILL_EVALS`` or ``SKILL_EVAL_EXCLUDE``."""
    wiki_dirs = {p.parent.name for p in (REPO / "skills").glob("wiki-*/SKILL.md")}
    covered = {c["skill"] for c in SKILL_EVALS}
    assert wiki_dirs == covered | SKILL_EVAL_EXCLUDE, (
        f"wiki skill dirs must equal SKILL_EVALS ∪ SKILL_EVAL_EXCLUDE; "
        f"only in dirs: {wiki_dirs - covered - SKILL_EVAL_EXCLUDE}; "
        f"only in eval: {covered - wiki_dirs}; "
        f"only in exclude: {SKILL_EVAL_EXCLUDE - wiki_dirs}"
    )


def test_commands_and_wiki_skills_glob_non_empty() -> None:
    """Playbook parity: at least one command file and one wiki skill (sanity)."""
    cmds = list((REPO / "commands").glob("*.md"))
    skills = list((REPO / "skills").glob("wiki-*/SKILL.md"))
    assert len(cmds) >= 1, "expected commands/*.md"
    assert len(skills) >= 1, "expected skills/wiki-*/SKILL.md"
