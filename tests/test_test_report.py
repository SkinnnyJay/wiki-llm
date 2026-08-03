"""Regression tests for executable-documentation report classification."""

from __future__ import annotations

from lib.test_report import _classify_argv


def test_report_skips_blocking_foreground_viewer_server() -> None:
    action, reason = _classify_argv(["build-og", "--serve"], network=False)

    assert action == "skip"
    assert "foreground" in reason


def test_report_runs_nonblocking_viewer_build() -> None:
    action, reason = _classify_argv(["build-og", "--serve-background"], network=False)

    assert action == "run"
    assert reason == ""
