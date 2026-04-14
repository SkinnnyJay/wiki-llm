"""Rubric dimensions: JSON overrides + automated proxies from capabilities and run outcome."""

from __future__ import annotations

import importlib.metadata
import json
import re
from pathlib import Path
from typing import Any

from benchmarks.peers.base import DimensionScores, PeerCapabilities


def _rubric_path() -> Path:
    return Path(__file__).resolve().parent / "rubric_overrides.json"


def load_rubric_overrides() -> dict[str, Any]:
    p = _rubric_path()
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _clamp_10(x: float | None) -> float | None:
    if x is None:
        return None
    return max(0.0, min(10.0, float(x)))


def _integration_score(cap: PeerCapabilities) -> float:
    n = 0.0
    if cap.python_sdk:
        n += 3.0
    if cap.http_api:
        n += 2.5
    if cap.cli:
        n += 2.0
    if cap.mcp:
        n += 2.5
    return min(10.0, n)


def _simplicity_proxy(cap: PeerCapabilities, *, heavy_deps: bool) -> float:
    base = 7.0 if cap.python_sdk else 4.0
    if heavy_deps:
        base -= 2.0
    if cap.requires_network:
        base -= 0.5
    return max(0.0, min(10.0, base))


def _arch_maturity_proxy(peer_id: str, cap: PeerCapabilities) -> float | None:
    pkg_map = {
        "mem0": "mem0ai",
    }
    pkg = pkg_map.get(peer_id)
    if not pkg:
        return None
    try:
        v = importlib.metadata.version(pkg)
    except importlib.metadata.PackageNotFoundError:
        return None
    m = re.match(r"^(\d+)", v)
    major = int(m.group(1)) if m else 1
    score = 7.0 if major >= 1 else 5.5
    if cap.license_hint.lower() in ("apache-2.0", "mit", "bsd"):
        score = min(10.0, score + 0.5)
    return min(10.0, score)


def _data_integrity_proxy(cap: PeerCapabilities, *, roundtrip_ok: bool | None) -> float:
    if roundtrip_ok is True:
        return 9.0
    if roundtrip_ok is False:
        return 4.0
    if cap.verbatim_ingest:
        return 7.0
    return 5.0


def merge_dimension_scores(
    peer_id: str,
    cap: PeerCapabilities,
    *,
    heavy_deps: bool = False,
    roundtrip_ok: bool | None = None,
    recall_ran: bool = False,
) -> DimensionScores:
    """Merge editorial JSON overrides with automated proxies."""
    overrides = load_rubric_overrides()
    peer_o = (overrides.get("peers") or {}).get(peer_id) or {}
    ov = peer_o.get("overrides") if isinstance(peer_o.get("overrides"), dict) else {}

    def dim(
        key: str,
        proxy: float | None,
    ) -> tuple[float | None, str]:
        if isinstance(ov, dict) and key in ov and isinstance(ov[key], (int, float)):
            src = str(ov.get(f"{key}_source") or "editorial")
            return _clamp_10(float(ov[key])), src
        if proxy is not None:
            return _clamp_10(proxy), "proxy"
        return None, "missing"

    di_p = _data_integrity_proxy(cap, roundtrip_ok=roundtrip_ok)
    si_p = _simplicity_proxy(cap, heavy_deps=heavy_deps)
    int_p = _integration_score(cap)
    am_p = _arch_maturity_proxy(peer_id, cap)

    di, s1 = dim("data_integrity", di_p)
    si, s2 = dim("simplicity", si_p)
    ig, s3 = dim("integration", int_p)
    am, s4 = dim("arch_maturity", am_p)

    src = {
        "data_integrity": s1,
        "simplicity": s2,
        "integration": s3,
        "arch_maturity": s4,
    }
    if not recall_ran and peer_o.get("skip_lme_note"):
        src["note"] = str(peer_o["skip_lme_note"])

    return DimensionScores(
        data_integrity=di,
        simplicity=si,
        integration=ig,
        arch_maturity=am,
        source=src,
    )


def dimensions_to_jsonable(ds: DimensionScores) -> dict[str, Any]:
    return {
        "data_integrity": ds.data_integrity,
        "simplicity": ds.simplicity,
        "integration": ds.integration,
        "arch_maturity": ds.arch_maturity,
        "overall": ds.overall(),
        "source": dict(ds.source),
    }
