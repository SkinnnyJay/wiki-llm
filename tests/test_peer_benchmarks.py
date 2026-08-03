"""Peer benchmark registry, dimensions, and skip behavior."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest
from lib.config_loader import DEFAULTS, deep_merge

from benchmarks.peer_lme import run_lme_peers
from benchmarks.peers.dimensions import dimensions_to_jsonable, merge_dimension_scores
from benchmarks.peers.registry import get_peer_adapter


def test_get_peer_supermemory_requires_an_explicit_headless_bridge() -> None:
    a = get_peer_adapter("supermemory", cfg=DEFAULTS)
    h = a.health()
    assert h.ok is False


def test_get_peer_supermemory_uses_configured_headless_bridge(monkeypatch) -> None:
    bridge_code = 'import json; print(json.dumps({"ranked_session_ids": ["S0"]}))'
    monkeypatch.setenv(
        "SUPERMEMORY_BENCH_CMD",
        f"{shlex.quote(sys.executable)} -c {shlex.quote(bridge_code)}",
    )
    adapter = get_peer_adapter("supermemory", cfg=DEFAULTS)

    assert adapter.health().ok is True
    assert adapter.ingest_and_query(
        sessions=[[{"role": "user", "content": "hello"}]],
        session_ids=["S0"],
        dates=["2020-01-01"],
        question="test?",
        n_fetch=5,
        run_idx=0,
        run_cache=None,
    ) == ["S0"]


def test_peer_bridge_does_not_interpret_shell_control_operators(monkeypatch, tmp_path: Path) -> None:
    marker = tmp_path / "must-not-exist"
    bridge_code = 'import json; print(json.dumps({"ranked_session_ids": ["S0"]}))'
    monkeypatch.setenv(
        "SUPERMEMORY_BENCH_CMD",
        f"{shlex.quote(sys.executable)} -c {shlex.quote(bridge_code)} ; touch {shlex.quote(str(marker))}",
    )
    adapter = get_peer_adapter("supermemory", cfg=DEFAULTS)

    result = adapter.ingest_and_query(
        sessions=[[{"role": "user", "content": "hello"}]],
        session_ids=["S0"],
        dates=["2020-01-01"],
        question="test?",
        n_fetch=5,
        run_idx=0,
        run_cache=None,
    )

    assert result == ["S0"]
    assert not marker.exists()


def test_peer_bridge_rejects_non_object_json(monkeypatch) -> None:
    monkeypatch.setenv("SUPERMEMORY_BENCH_CMD", "printf '[]'")
    adapter = get_peer_adapter("supermemory", cfg=DEFAULTS)

    with pytest.raises(RuntimeError, match="must return a JSON object"):
        adapter.ingest_and_query(
            sessions=[],
            session_ids=[],
            dates=[],
            question="test?",
            n_fetch=5,
            run_idx=0,
            run_cache=None,
        )


def test_merge_dimensions_has_sources() -> None:
    from benchmarks.peers.base import PeerCapabilities

    cap = PeerCapabilities(
        peer_id="mem0",
        python_sdk=True,
        http_api=True,
        verbatim_ingest=True,
        license_hint="apache-2.0",
    )
    ds = merge_dimension_scores("mem0", cap, heavy_deps=True, roundtrip_ok=None, recall_ran=True)
    j = dimensions_to_jsonable(ds)
    assert j.get("integration") is not None
    assert j["source"].get("integration") in ("proxy", "editorial")


def test_run_lme_peers_skips_supermemory(tmp_path: Path) -> None:
    cfg = deep_merge(DEFAULTS, {})
    cfg.setdefault("benchmark", {})["enabled"] = True
    cfg.setdefault("metrics", {})["enabled"] = False

    tiny = [
        {
            "question_id": "q0",
            "question": "test?",
            "haystack_sessions": [[{"role": "user", "content": "hello"}]],
            "haystack_session_ids": ["S0"],
            "haystack_dates": ["2020-01-01"],
            "answer_session_ids": ["S0"],
        }
    ]
    out = run_lme_peers(
        tiny,
        tmp_path,
        cfg,
        peer_ids=["supermemory"],
        limit=1,
        top_k=5,
        strict_peers=False,
    )
    assert out["suite"] == "lme_peers"
    sm = out["peers"].get("supermemory")
    assert sm is not None
    assert sm.get("skipped") is True
    assert sm.get("summary") is None
    assert "dimensions" in sm


def test_registry_unknown_peer() -> None:
    a = get_peer_adapter("not-a-real-peer", cfg=DEFAULTS)
    assert a.health().ok is False
