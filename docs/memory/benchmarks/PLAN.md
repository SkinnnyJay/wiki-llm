# Benchmark roadmap — LME 100%, metrics, reports, comparisons

Consolidated plan for retrieval benchmarks, failure reduction, metrics strategy, Markdown reports, chartable run history, and external comparisons. **Memory Palace / quotes suite** is deferred until LME hits 100% on the current harness.

---

## Metrics strategy (no duplicate vault “memory” metrics)

- **Session memory** (`raw/memory/`, `memory` CLI) does **not** write to the metrics JSONL. There is no separate “memory metrics database” for chat memory.
- **Single operational store** today: vault **`storage.metrics_db`** (default **`llm-wiki/.metrics.jsonl`**), append-only JSONL via [`MetricsRecorder`](../../../scripts/lib/metrics.py).
- **Benchmarks** use [`record_benchmark_metrics`](../../../benchmarks/bench_harness.py): keys like **`benchmark.lme.recall_at_5`**, **`benchmark.lme.failures`**, etc. The harness **merges `metrics.enabled: true`** for those writes so runs still record when vault `metrics.enabled` is false, unless **`benchmark.auto_record_metrics`** is off.
- **Separation without duplication:** filter by **`key` prefix** (`benchmark.*` vs `search.*`, `mcp.*`, `kg.*`). Same file, distinct namespaces.
- **Resolved — optional repo mirror:** **`benchmark.append_repo_runs_jsonl`: true** appends one JSON line per benchmark run to **`docs/memory/benchmarks/metrics/runs.jsonl`** in the plugin repo (git-friendly charts). **Canonical store for a vault** remains **`storage.metrics_db`** (default **`.metrics.jsonl`**) with **`benchmark.*`** and operational keys; the repo file is an optional duplicate stream for contributors, not a second source of truth.

---

## Phase 1 — Diagnose LME failures (blocking)

- **Artifact:** `llm-wiki/.benchmarks/lme_failures.jsonl` per run.
- **Per failure:** classify **P** (pool miss — gold not in candidate paths), **R** (rank miss — in pool, not top-5), **M** (multi-gold / ambiguity), **L** (LLM/API/parse skip).
- **Instrument once:** log whether gold appears in `paths` / top-`max_candidates` before session ordering; verify **`LLM_WIKI_BENCHMARK_LLM`** path actually invokes rerank when expected.
- **Playbook:** P → retrieval/index/fusion; R → ordering + rerank; L → logging and retries.

---

## Phase 2 — Reduce failures toward LME R@5 = 1.0 (500 questions)

- Tune fusion / index / rerank per Phase 1 buckets; document **winning config** in [`benchmarks/README.md`](../../../benchmarks/README.md).
- Track **`failures`** and optional **`failure_bucket_counts`** over runs for charts.

---

## Phase 3 — Reports and chartable metrics

- **Markdown:** per-run reports under **`docs/memory/benchmarks/runs/`** (or similar), sections: metadata, scores, Δ vs previous, link to failures log.
- **Chart-friendly:** append **`docs/memory/benchmarks/metrics/runs.jsonl`** (or enrich vault `.metrics.jsonl` only — decide at implement time) with `ts`, `suite`, `backend`, `compressor`, `limit`, `llm`, `invoke`, `config_hash`, `recall_at_*`, `failures`, `elapsed_s`.
- **CLI:** extend **`llm-wiki benchmark report`** (or add **`compare`**) for best/worst and config diff.
- **End report:** summary Markdown under **`docs/memory/benchmarks/`** after milestone runs.

---

## Phase 4 — External comparisons (documentation)

- **`comparisons.md`** in this folder: table of **other systems** (Memory Palace, etc.) with **benchmark name**, **metric**, **score**, **primary source**, **date**, **comparability notes** (same dataset split or not).
- Start with methodology caveats; fill scores as verified from papers/READMEs — not from scraped HTML alone.

---

## Phase 5 — LoCoMo & ConvoMem (after LME target met)

- Dataset download, conversion, and scoring are wired (`locomo_bench.py`, `convomem_bench.py`).
- Tested with minimal fixtures; full network runs require HuggingFace / manual data.
- Expand coverage and tune scoring thresholds as real data accumulates.

---

## Phase 6 — Memory Palace / quotes (deferred)

- Only after LME acceptance; define format from upstream eval, add suite + docs here.

---

## Success criteria

- **LME:** `recall_at_5 = 1.0`, `failures = 0` on full 500 with documented config (subject to theoretical “gold never in pool” cap).
- **Ops:** One metrics story: vault **`.metrics.jsonl`** holds `benchmark.*` and operational keys (prefix namespaces); optional **`runs.jsonl`** in-repo only when `append_repo_runs_jsonl` is enabled — **no** session-memory metric DB (session memory does not write metrics).
