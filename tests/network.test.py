# tests/network.test.py
"""Optional tests that touch the network. Enable with RUN_NETWORK_TESTS=1 or smoke-test --network."""

from __future__ import annotations

import urllib.error
import urllib.request

import pytest


@pytest.mark.network
def test_https_get_example_com() -> None:
    """Minimal reachability check (public HTTPS)."""
    req = urllib.request.Request("https://example.com", headers={"User-Agent": "llm-wiki-tests"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            assert resp.status == 200
    except urllib.error.URLError as e:
        pytest.fail(f"network reachability check failed: {e}")
