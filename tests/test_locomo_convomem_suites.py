"""Smoke tests for LoCoMo conversion, ConvoMem pending path, and suite help."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from benchmarks.convomem_bench import run_convomem
from benchmarks.locomo_bench import locomo_to_lme_entries
from benchmarks.suite_help import describe_benchmark_suites


def test_locomo_to_lme_entries_fixture():
    raw = json.loads((REPO / "benchmarks/fixtures/locomo_min.json").read_text(encoding="utf-8"))
    entries = locomo_to_lme_entries(raw)
    assert len(entries) == 1
    e = entries[0]
    assert e["question_id"] == "locomo_c0_q0"
    assert "violin" in e["question"].lower() or "instrument" in e["question"].lower()
    assert e["answer_session_ids"] == ["S1"]
    assert e["haystack_session_ids"] == ["S1"]


def test_convomem_pending_without_data(tmp_path):
    from lib.config_loader import DEFAULTS, deep_merge

    vault = tmp_path / "llm-wiki"
    vault.mkdir()
    cfg = deep_merge(DEFAULTS, {})
    out = run_convomem(vault, cfg, data_path=None)
    assert out["summary"]["status"] == "pending"


def test_convomem_tiny_fixture_shape():
    raw = json.loads((REPO / "benchmarks/fixtures/convomem_tiny.json").read_text(encoding="utf-8"))
    assert isinstance(raw, list) and len(raw) == 1
    e = raw[0]
    for k in (
        "haystack_sessions",
        "haystack_session_ids",
        "haystack_dates",
        "question",
        "answer_session_ids",
    ):
        assert k in e


def test_suite_help_text_mentions_suites():
    text = describe_benchmark_suites()
    assert "LongMemEval" in text and "LoCoMo" in text and "ConvoMem" in text
