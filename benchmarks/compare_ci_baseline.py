#!/usr/bin/env python3
"""Compare an LME smoke summary against a tracked CI baseline.

Fails when actual recall_at_5 < max(min_recall_at_5, recall_at_5 - epsilon).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_summary(*, summary: Path | None, vault: Path | None) -> dict:
    if summary is not None:
        data = json.loads(summary.read_text(encoding="utf-8"))
        return data["summary"] if isinstance(data.get("summary"), dict) else data
    if vault is None:
        raise SystemExit("Provide --summary PATH or --vault PATH (reads latest .benchmarks/runs/*.json)")
    runs_dir = vault / ".benchmarks" / "runs"
    runs = sorted(runs_dir.glob("*.json")) if runs_dir.is_dir() else []
    if not runs:
        raise SystemExit(f"No benchmark run sidecar under {runs_dir}")
    data = json.loads(runs[-1].read_text(encoding="utf-8"))
    return data["summary"] if isinstance(data.get("summary"), dict) else data


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", type=Path, required=True, help="Tracked baseline JSON")
    ap.add_argument("--summary", type=Path, default=None, help="Smoke summary or sidecar JSON")
    ap.add_argument("--vault", type=Path, default=None, help="Vault with .benchmarks/runs sidecars")
    args = ap.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    summary = _load_summary(summary=args.summary, vault=args.vault)

    try:
        actual = float(summary["recall_at_5"])
    except (KeyError, TypeError, ValueError) as exc:
        print(f"Smoke summary missing recall_at_5: {exc}", file=sys.stderr)
        return 2

    recorded = float(baseline.get("recall_at_5", baseline.get("min_recall_at_5", 0.0)))
    epsilon = float(baseline.get("epsilon", 0.05))
    min_floor = float(baseline.get("min_recall_at_5", 0.0))
    threshold = max(min_floor, recorded - epsilon)

    print(
        f"suite={baseline.get('suite')} limit={baseline.get('limit')} "
        f"recall_at_5={actual} threshold={threshold} "
        f"(baseline.recall_at_5={recorded} epsilon={epsilon} min_recall_at_5={min_floor})"
    )
    if actual < threshold:
        print(
            f"FAIL: recall_at_5 {actual} is below threshold {threshold}",
            file=sys.stderr,
        )
        return 1
    print("OK: within baseline tolerance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
