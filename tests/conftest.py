"""Pytest hooks: optional network and Claude CLI test suites."""

from __future__ import annotations

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "network: uses the network (enabled via RUN_NETWORK_TESTS=1 or llm-wiki smoke-test --network)",
    )
    config.addinivalue_line(
        "markers",
        "claude: requires claude CLI (enabled via RUN_CLAUDE_TESTS=1 or llm-wiki smoke-test --claude)",
    )


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
