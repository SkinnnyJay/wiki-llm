"""Peer benchmark registry, dimensions, and skip behavior."""

from __future__ import annotations

from pathlib import Path

from benchmarks.peer_lme import run_lme_peers
from benchmarks.peers.dimensions import dimensions_to_jsonable, merge_dimension_scores
from benchmarks.peers.registry import get_peer_adapter
from lib.config_loader import DEFAULTS, deep_merge


def test_get_peer_supermemory_skips() -> None:
    a = get_peer_adapter("supermemory", cfg=DEFAULTS)
    h = a.health()
    assert h.ok is False


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
