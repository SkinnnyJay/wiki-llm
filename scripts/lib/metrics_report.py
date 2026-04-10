"""Build metrics HTML report (Chart.js) and text/JSON summaries from JSONL."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from lib.config_loader import resolve_storage_path
from lib.paths import plugin_root


def _default_since_iso(days: int = 30) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iter_benchmark_lme_snapshots(
    vault: Path,
    cfg: dict[str, Any],
    *,
    since: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Lines for ``benchmark.lme.recall_at_5`` (one row per LME run)."""
    recs = load_metrics_records(vault, cfg, since=since, limit=0)
    rows = [r for r in recs if str(r.get("key", "")) == "benchmark.lme.recall_at_5"]
    if limit > 0:
        return rows[-limit:]
    return rows


def load_metrics_records(
    vault: Path,
    cfg: dict[str, Any],
    *,
    since: str | None = None,
    key: str | None = None,
    limit: int = 0,
) -> list[dict[str, Any]]:
    """Read metrics JSONL from storage path (works even when metrics.enabled is false)."""
    path = resolve_storage_path(vault, cfg, "metrics_db")
    if not path.is_file():
        return []
    results: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if key and rec.get("key") != key:
                    continue
                if since and rec.get("ts", "") < since:
                    continue
                results.append(rec)
    except OSError:
        return []
    if limit > 0:
        return results[-limit:]
    return results


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    k = (n - 1) * p / 100.0
    f = int(math.floor(k))
    c = min(f + 1, n - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _to_float(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    return None


def aggregate_for_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Group by key: counts, numeric stats, non-numeric keys."""
    by_key: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        k = str(r.get("key", "?"))
        by_key.setdefault(k, []).append(r)

    rows: list[dict[str, Any]] = []
    for k, items in sorted(by_key.items()):
        nums: list[float] = []
        for r in items:
            f = _to_float(r.get("value"))
            if f is not None:
                nums.append(f)
        nums.sort()
        row: dict[str, Any] = {"key": k, "count": len(items)}
        if nums:
            row["numeric"] = True
            row["avg"] = round(sum(nums) / len(nums), 3)
            row["p50"] = round(_percentile(nums, 50), 3)
            row["p90"] = round(_percentile(nums, 90), 3)
            row["p99"] = round(_percentile(nums, 99), 3)
        else:
            row["numeric"] = False
        rows.append(row)

    ts_list = [r.get("ts", "") for r in records if r.get("ts")]
    first_ts = min(ts_list) if ts_list else ""
    last_ts = max(ts_list) if ts_list else ""
    return {
        "rows": rows,
        "record_count": len(records),
        "key_count": len(by_key),
        "first_ts": first_ts,
        "last_ts": last_ts,
    }


def build_metrics_summary(
    vault: Path,
    cfg: dict[str, Any],
    *,
    since: str | None = None,
    key: str | None = None,
    as_json: bool = False,
) -> str | dict[str, Any]:
    """
    Inline report for chat/terminal. Default time range: last 30 days when *since* is None.
    """
    eff_since = since if since is not None else _default_since_iso(30)
    records = load_metrics_records(vault, cfg, since=eff_since, key=key)
    agg = aggregate_for_summary(records)
    path = resolve_storage_path(vault, cfg, "metrics_db")
    size_bytes = path.stat().st_size if path.is_file() else 0

    payload: dict[str, Any] = {
        "since": eff_since,
        "key_filter": key,
        "record_count": agg["record_count"],
        "key_count": agg["key_count"],
        "first_ts": agg["first_ts"],
        "last_ts": agg["last_ts"],
        "file_kb": round(size_bytes / 1024.0, 2),
        "rows": agg["rows"],
    }
    if as_json:
        return payload

    if agg["first_ts"] and agg["last_ts"]:
        title_range = f"{agg['first_ts'][:10]} to {agg['last_ts'][:10]}"
    else:
        title_range = "no records"
    lines = [
        f"## Metrics Summary ({title_range})",
        "",
        "| Key | Count | Avg | P50 | P90 | P99 |",
        "|-----|------:|----:|----:|----:|----:|",
    ]
    for row in agg["rows"]:
        if row.get("numeric"):
            lines.append(
                f"| {row['key']} | {row['count']} | {row['avg']} | {row['p50']} | {row['p90']} | {row['p99']} |"
            )
        else:
            lines.append(f"| {row['key']} | {row['count']} | — | — | — | — |")
    lines.append("")
    lines.append(f"Records: {agg['record_count']} | File: {payload['file_kb']} KB | Keys: {agg['key_count']}")
    return "\n".join(lines)


def _bucket_label(ts: str, use_day: bool) -> str:
    """Normalize ISO ts to bucket key for charts."""
    if not ts or len(ts) < 10:
        return ts
    if use_day:
        return ts[:10]
    # hour
    if "T" in ts:
        return ts[:13]  # YYYY-MM-DDTHH
    return ts[:10]


def _build_timeline_series(
    records: list[dict[str, Any]],
    *,
    numeric_keys_only: bool = True,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Returns sorted bucket labels and series {key, data aligned to labels}."""
    if not records:
        return [], []
    ts_list = [r.get("ts", "") for r in records if r.get("ts")]
    if not ts_list:
        return [], []
    first = min(ts_list)
    last = max(ts_list)
    try:
        d0 = datetime.fromisoformat(first.replace("Z", "+00:00"))
        d1 = datetime.fromisoformat(last.replace("Z", "+00:00"))
        span_days = max(1, (d1 - d0).days + 1)
    except ValueError:
        span_days = 30
    use_day = span_days > 7

    # keys with at least one numeric value
    key_nums: dict[str, list[tuple[str, float]]] = {}
    for r in records:
        k = str(r.get("key", "?"))
        v = _to_float(r.get("value"))
        if v is None:
            if numeric_keys_only:
                continue
        ts = r.get("ts", "")
        if not ts:
            continue
        b = _bucket_label(ts, use_day)
        val = v if v is not None else 0.0
        key_nums.setdefault(k, []).append((b, val))

    if not key_nums:
        return [], []

    all_buckets: set[str] = set()
    for pairs in key_nums.values():
        for b, _ in pairs:
            all_buckets.add(b)
    labels = sorted(all_buckets)

    # average values per bucket per key
    series: list[dict[str, Any]] = []
    palette = ["#38bdf8", "#a78bfa", "#67C4FF", "#9B82FF", "#69BFFF", "#c084fc", "#22d3ee", "#818cf8"]
    for idx, (k, pairs) in enumerate(sorted(key_nums.items())[:12]):
        bucket_sum: dict[str, list[float]] = {}
        for b, val in pairs:
            bucket_sum.setdefault(b, []).append(val)
        data = []
        for lab in labels:
            vals = bucket_sum.get(lab, [])
            data.append(round(sum(vals) / len(vals), 4) if vals else None)
        series.append({
            "key": k,
            "label": k,
            "data": data,
            "borderColor": palette[idx % len(palette)],
            "backgroundColor": palette[idx % len(palette)] + "33",
        })
    return labels, series


def _latency_percentile_chart_data(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Bar chart: p50/p90/p99 for keys ending in _ms or numeric rows."""
    ms_rows = [r for r in rows if r.get("numeric") and str(r["key"]).endswith("_ms")]
    if not ms_rows:
        ms_rows = [r for r in rows if r.get("numeric")]
    labels = [r["key"] for r in ms_rows[:12]]
    return {
        "labels": labels,
        "p50": [r.get("p50", 0) for r in ms_rows[:12]],
        "p90": [r.get("p90", 0) for r in ms_rows[:12]],
        "p99": [r.get("p99", 0) for r in ms_rows[:12]],
    }


def build_metrics_report(
    vault: Path,
    cfg: dict[str, Any],
    out_dir: Path,
    *,
    since: str | None = None,
    key: str | None = None,
) -> Path:
    """
    Write Chart.js HTML dashboard to out_dir/index.html.
    Default time range: last 30 days when *since* is None.
    """
    eff_since = since if since is not None else _default_since_iso(30)
    records = load_metrics_records(vault, cfg, since=eff_since, key=key)
    agg = aggregate_for_summary(records)
    path = resolve_storage_path(vault, cfg, "metrics_db")
    size_bytes = path.stat().st_size if path.is_file() else 0

    labels, series = _build_timeline_series(records)
    dist_labels = list(sorted({r.get("key", "?") for r in records}))
    dist_counts = []
    for kl in dist_labels:
        dist_counts.append(sum(1 for r in records if r.get("key") == kl))
    lat_data = _latency_percentile_chart_data(agg["rows"])

    pname = str((cfg.get("persona") or {}).get("name") or "Gennie")
    generated = datetime.now(timezone.utc).isoformat()

    payload: dict[str, Any] = {
        "meta": {
            "persona_name": pname,
            "generated_at": generated,
            "vault_path": str(vault.resolve()),
            "metrics_path": str(path),
            "since": eff_since,
            "key_filter": key,
            "record_count": agg["record_count"],
            "key_count": agg["key_count"],
            "first_ts": agg["first_ts"],
            "last_ts": agg["last_ts"],
            "size_bytes": size_bytes,
        },
        "timeline": {"labels": labels, "series": series},
        "distribution": {"labels": dist_labels, "counts": dist_counts},
        "latency_bars": lat_data,
    }

    tpl_root = plugin_root() / "templates" / "metrics-report"
    tpl_html = tpl_root / "index.html"
    if not tpl_html.is_file():
        raise FileNotFoundError(f"Missing metrics report template: {tpl_html}")

    raw = tpl_html.read_text(encoding="utf-8")
    json_blob = json.dumps(payload, ensure_ascii=False)
    if "__METRICS_DATA_JSON__" not in raw:
        raise ValueError("Template missing __METRICS_DATA_JSON__ placeholder")
    html_out = raw.replace("__METRICS_DATA_JSON__", json_blob)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "index.html"
    out_path.write_text(html_out, encoding="utf-8")
    return out_path
