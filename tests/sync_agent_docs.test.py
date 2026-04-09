# tests/sync_agent_docs.test.py
"""Agent doc sync verification (plugin repo)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))


def test_verify_agent_docs_matches_shared():
    from sync_agent_docs import verify_agent_docs

    assert verify_agent_docs(REPO, quiet=True) == 0
