# Run artifacts (JSON + optional Markdown)

**JSON** — Tracked snapshots of benchmark summaries (LME rerank experiments, mode compares, validated “best so far” rows) live here as **`*.json`**. Example: **`rerank_cli_validated_2026-04-10.json`** backs the narrative in **[`../lme_misses_blocking_100.md`](../lme_misses_blocking_100.md)**. Prefer small, reviewable files; regenerate after serious runs rather than bloating git with every trial.

**Markdown (optional)** — Drop milestone narratives (e.g. `lme_before_after_all_models_2026-04-09.md`) with metadata, scores, and deltas vs the previous run. The CLI records metrics in vault **`.metrics.jsonl`** and optional **`docs/memory/benchmarks/metrics/runs.jsonl`** when `benchmark.append_repo_runs_jsonl` is enabled; this folder is for human-readable stories and machine-readable JSON you want versioned together.
