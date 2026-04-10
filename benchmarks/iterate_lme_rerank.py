#!/usr/bin/env python3
"""
Drive many LME + rerank_llm trials, log metrics, emit JSONL/CSV/HTML chart.

Usage (from repo root):
  LLM_WIKI_BENCHMARK_LLM=1 python3 benchmarks/iterate_lme_rerank.py \\
    --iterations 150 --limit 50 --out-dir docs/memory/benchmarks/runs

Full headline eval (slow):
  --limit 0

Dry-run (print trial schedule only):
  --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lib.config_loader import DEFAULTS, deep_merge


def _trial_schedule(n: int) -> list[dict[str, Any]]:
    """Deterministic n micro-knob combinations (rerank_llm patch only)."""
    fuse_w = [0.25, 0.28, 0.30, 0.32, 0.35, 0.38, 0.40, 0.42, 0.45, 0.48]
    max_picks = [5, 6, 7, 8, 9, 10, 11, 12]
    max_chars = [2800, 3200, 3600, 4000, 4400, 4800, 5200]
    adaptive_thr = [0.40, 0.45, 0.50, 0.55, 0.60]
    out: list[dict[str, Any]] = []
    i = 0
    while len(out) < n:
        fw = fuse_w[i % len(fuse_w)]
        mp = max_picks[(i // len(fuse_w)) % len(max_picks)]
        mc = max_chars[(i // (len(fuse_w) * len(max_picks))) % len(max_chars)]
        ath = adaptive_thr[(i // (len(fuse_w) * len(max_picks) * len(max_chars))) % len(adaptive_thr)]
        if i % 2 == 0:
            base: dict[str, Any] = {
                "fuse_original_rrf": True,
                "fuse_original_weight": fw,
                "fuse_rrf_k": 60,
                "max_picks": mp,
                "max_chars": mc,
                "invoke_when": "always",
            }
        else:
            base = {
                "fuse_original_rrf": True,
                "fuse_original_weight": fw,
                "fuse_rrf_k": 60,
                "max_picks": mp,
                "max_chars": mc,
                "invoke_when": "adaptive",
                "adaptive_confidence_threshold": ath,
            }
        out.append(base)
        i += 1
    return out[:n]


def _is_better(a: dict[str, Any], b: dict[str, Any]) -> bool:
    ra = float(a.get("recall_at_5", 0))
    rb = float(b.get("recall_at_5", 0))
    if ra > rb:
        return True
    if ra < rb:
        return False
    fa = int(a.get("failures", 9999))
    fb = int(b.get("failures", 9999))
    return fa < fb


def _html_report(rows: list[dict[str, Any]], best: dict[str, Any] | None) -> str:
    lab = json.dumps([r.get("iteration", i) for i, r in enumerate(rows)])
    r5 = json.dumps([float(r.get("summary", {}).get("recall_at_5", 0)) for r in rows])
    fl = json.dumps([int(r.get("summary", {}).get("failures", 0)) for r in rows])
    best_line = ""
    if best:
        best_line = (
            f"<p><strong>Best</strong>: R@5={best.get('recall_at_5')} failures={best.get('failures')} "
            f"<code>{json.dumps(best.get('trial', {}))}</code></p>"
        )
    rows_json = json.dumps(rows, default=str)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>LME rerank iterations</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
body {{ font-family: system-ui, sans-serif; margin: 1rem; max-width: 1200px; }}
canvas {{ max-height: 400px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
td, th {{ border: 1px solid #ccc; padding: 4px; }}
tr.best {{ background: #e8f5e9; }}
code {{ font-size: 11px; word-break: break-all; }}
</style>
</head>
<body>
<h1>LME rerank iterations</h1>
<p>{datetime.now(timezone.utc).isoformat()}</p>
{best_line}
<canvas id="c1"></canvas>
<canvas id="c2"></canvas>
<h2>Runs</h2>
<table id="tbl"><thead><tr><th>#</th><th>R@5</th><th>fail</th><th>elapsed_s</th><th>best_row</th><th>trial</th></tr></thead><tbody></tbody></table>
<script>
const ROWS = {rows_json};
const L = {lab}, R5 = {r5}, F = {fl};
new Chart(document.getElementById('c1'), {{
  type: 'line',
  data: {{ labels: L, datasets: [{{ label: 'recall_at_5', data: R5, borderColor: '#1565c0' }}] }},
  options: {{ plugins: {{ title: {{ display: true, text: 'Recall@5' }} }} }}
}});
new Chart(document.getElementById('c2'), {{
  type: 'line',
  data: {{ labels: L, datasets: [{{ label: 'failures', data: F, borderColor: '#c62828' }}] }},
  options: {{ plugins: {{ title: {{ display: true, text: 'Failures' }} }} }}
}});
const tb = document.querySelector('#tbl tbody');
ROWS.forEach((r, i) => {{
  const tr = document.createElement('tr');
  if (r.best_so_far) tr.className = 'best';
  const s = r.summary || {{}};
  const t = document.createElement('td'); t.textContent = String(i);
  const t1 = document.createElement('td'); t1.textContent = String(s.recall_at_5 ?? '');
  const t2 = document.createElement('td'); t2.textContent = String(s.failures ?? '');
  const t3 = document.createElement('td'); t3.textContent = String(s.elapsed_s ?? '');
  const t4 = document.createElement('td'); t4.textContent = r.best_so_far ? 'yes' : '';
  const t5 = document.createElement('td');
  const code = document.createElement('code'); code.textContent = JSON.stringify(r.trial || {{}}).slice(0, 400);
  t5.appendChild(code);
  tr.appendChild(t); tr.appendChild(t1); tr.appendChild(t2); tr.appendChild(t3); tr.appendChild(t4); tr.appendChild(t5);
  tb.appendChild(tr);
}});
</script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Iterate LME rerank micro-knobs with logging + HTML chart.")
    ap.add_argument("--iterations", type=int, default=150, help="Number of trials (default 150)")
    ap.add_argument("--limit", type=int, default=50, help="LME --limit (0 = full 500)")
    ap.add_argument("--vault", type=Path, default=None, help="Vault dir (default: temp dir)")
    ap.add_argument("--out-dir", type=Path, default=Path("docs/memory/benchmarks/runs"), help="Output directory")
    ap.add_argument("--dry-run", action="store_true", help="Print schedule; do not run benchmarks")
    ap.add_argument("--no-llm-env", action="store_true", help="Do not set LLM_WIKI_BENCHMARK_LLM=1")
    args = ap.parse_args()

    if not args.no_llm_env:
        os.environ.setdefault("LLM_WIKI_BENCHMARK_LLM", "1")

    trials = _trial_schedule(args.iterations)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / f"iteration_lme_rerank_{ts}.jsonl"
    csv_path = out_dir / f"iteration_lme_rerank_{ts}.csv"
    html_path = out_dir / f"iteration_lme_rerank_{ts}.html"

    if args.dry_run:
        for i, t in enumerate(trials[: min(20, len(trials))]):
            print(f"{i}: {json.dumps(t)}")
        print(f"... ({len(trials)} total) — would write {jsonl_path.name}")
        return 0

    from benchmarks.lme_bench import download_dataset, run_lme

    vault = args.vault
    if vault is None:
        vault = Path(tempfile.mkdtemp(prefix="lme_iter_"))
    else:
        vault = Path(vault).resolve()
        vault.mkdir(parents=True, exist_ok=True)

    cfg0 = deep_merge(DEFAULTS, {})
    cfg0.setdefault("benchmark", {})["search"] = {
        **(cfg0.get("benchmark") or {}).get("search", {}),
        "rerank_llm": {
            **(cfg0.get("benchmark") or {}).get("search", {}).get("rerank_llm", {}),
            "enabled": True,
            "benchmark_auto": True,
        },
    }

    cache = Path(
        os.path.expanduser(
            (cfg0.get("benchmark") or {}).get("data_cache_dir", "~/.cache/llm-wiki-benchmarks")
        )
    )
    data_path = download_dataset(cache)

    rows: list[dict[str, Any]] = []
    best_summary: dict[str, Any] | None = None
    best_trial: dict[str, Any] | None = None

    with jsonl_path.open("w", encoding="utf-8") as fjsonl, csv_path.open(
        "w", encoding="utf-8", newline=""
    ) as fcsv:
        w = csv.writer(fcsv)
        w.writerow(
            [
                "iteration",
                "recall_at_5",
                "failures",
                "elapsed_s",
                "ndcg_at_5",
                "trial_json",
                "best_so_far",
            ]
        )

        for it, trial in enumerate(trials):
            cfg = deep_merge(cfg0, {})
            rl = {**(cfg.get("benchmark") or {}).get("search", {}).get("rerank_llm", {}), **trial}
            cfg.setdefault("benchmark", {})["search"] = {
                **(cfg.get("benchmark") or {}).get("search", {}),
                "rerank_llm": rl,
            }
            t0 = time.monotonic()
            try:
                result = run_lme(
                    data_path,
                    vault,
                    cfg,
                    backend="fts5",
                    compressor_name="raw",
                    limit=args.limit,
                    top_k=5,
                )
            except Exception as exc:
                rec = {
                    "iteration": it,
                    "trial": trial,
                    "error": str(exc),
                    "summary": {},
                    "best_so_far": False,
                }
                rows.append(rec)
                fjsonl.write(json.dumps(rec, default=str) + "\n")
                w.writerow([it, "", "", "", "", json.dumps(trial), False])
                print(f"[{it + 1}/{len(trials)}] ERROR {exc}", flush=True)
                continue

            summary = result.get("summary", {})
            wall = time.monotonic() - t0
            improved = False
            if best_summary is None:
                improved = True
            else:
                improved = _is_better(summary, best_summary)

            if improved:
                best_summary = dict(summary)
                best_trial = dict(trial)

            rec = {
                "iteration": it,
                "trial": trial,
                "summary": summary,
                "wall_s": round(wall, 2),
                "best_so_far": bool(improved),
                "rolling_best_r5": best_summary.get("recall_at_5") if best_summary else None,
                "rolling_best_failures": best_summary.get("failures") if best_summary else None,
            }
            rows.append(rec)
            fjsonl.write(json.dumps(rec, default=str) + "\n")
            w.writerow(
                [
                    it,
                    summary.get("recall_at_5"),
                    summary.get("failures"),
                    summary.get("elapsed_s"),
                    summary.get("ndcg_at_5"),
                    json.dumps(trial),
                    improved,
                ]
            )
            print(
                f"[{it + 1}/{len(trials)}] R@5={summary.get('recall_at_5')} "
                f"fail={summary.get('failures')} best={improved} trial={trial}",
                flush=True,
            )

    best_payload: dict[str, Any] = {
        "recall_at_5": best_summary.get("recall_at_5") if best_summary else None,
        "failures": best_summary.get("failures") if best_summary else None,
        "trial": best_trial,
        "summary": best_summary,
    }
    (out_dir / f"iteration_lme_rerank_{ts}_best.json").write_text(
        json.dumps(best_payload, indent=2, default=str),
        encoding="utf-8",
    )

    html_path.write_text(_html_report(rows, {**best_payload, "trial": best_trial}), encoding="utf-8")

    print(
        f"\nWrote:\n  {jsonl_path}\n  {csv_path}\n  {html_path}\n"
        f"  {out_dir / f'iteration_lme_rerank_{ts}_best.json'}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
