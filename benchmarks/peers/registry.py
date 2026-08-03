"""Resolve peer id → adapter instance."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from benchmarks.peers.base import PeerAdapter
from benchmarks.peers.mem0_adapter import Mem0PeerAdapter
from benchmarks.peers.stubs import (
    ExternalCmdPeerAdapter,
    UnavailablePeerAdapter,
)

KNOWN_PEERS = (
    "mem0",
    "mempalace",
    "claude-mem",
    "supermemory",
)


def default_peer_cache_root(cfg: dict[str, Any]) -> Path:
    bcfg = cfg.get("benchmark") or {}
    peers = bcfg.get("peers") or {}
    raw = peers.get("cache_dir") or "~/.cache/llm-wiki-benchmarks/peers"
    return Path(os.path.expanduser(str(raw))).resolve()


def get_peer_adapter(peer_id: str, *, cfg: dict[str, Any]) -> PeerAdapter:
    pid = str(peer_id).strip().lower().replace("_", "-")
    cache_root = default_peer_cache_root(cfg)

    if pid == "mem0":
        return Mem0PeerAdapter(cache_root=cache_root)

    if pid == "mempalace":
        if os.environ.get("MEMPALACE_BENCH_CMD"):
            return ExternalCmdPeerAdapter("mempalace", env_var="MEMPALACE_BENCH_CMD")
        return UnavailablePeerAdapter(
            "mempalace",
            "set MEMPALACE_BENCH_CMD to a JSON stdin/stdout script or use editorial rubric only",
        )

    if pid in ("claude-mem", "claude_mem"):
        if os.environ.get("CLAUDE_MEM_BENCH_CMD"):
            return ExternalCmdPeerAdapter("claude-mem", env_var="CLAUDE_MEM_BENCH_CMD")
        return UnavailablePeerAdapter(
            "claude-mem",
            "set CLAUDE_MEM_BENCH_CMD to run headless retrieval, or use editorial rubric only",
        )

    if pid == "supermemory":
        if os.environ.get("SUPERMEMORY_BENCH_CMD"):
            return ExternalCmdPeerAdapter("supermemory", env_var="SUPERMEMORY_BENCH_CMD")
        return UnavailablePeerAdapter(
            "supermemory",
            "set SUPERMEMORY_BENCH_CMD to a JSON stdin/stdout bridge for the Supermemory API",
        )

    return UnavailablePeerAdapter(peer_id, f"unknown peer: {peer_id}")
