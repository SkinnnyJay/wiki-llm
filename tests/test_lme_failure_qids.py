"""Contract tests for tracked LME misses that block R@5 = 100% (best run snapshot)."""

from __future__ import annotations

import json
from pathlib import Path

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "lme_misses_best_run.json"


def test_lme_misses_fixture_schema() -> None:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert data["failures"] == len(data["misses"])
    for m in data["misses"]:
        assert "question_id" in m
        assert m["failure_bucket"] in ("P", "R", "M", "L", "")
        assert isinstance(m.get("gold_sessions"), list)


def test_best_run_single_miss_is_multi_gold() -> None:
    """Best validated run (more_picks_fuse) left one multi-gold case."""
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert data["failures"] == 1
    assert data["misses"][0]["question_id"] == "gpt4_4929293b"
    assert data["misses"][0]["failure_bucket"] == "M"
    assert len(data["misses"][0]["gold_sessions"]) >= 2
