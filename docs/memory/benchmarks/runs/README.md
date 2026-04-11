# Run artifacts (JSON + optional Markdown)

**JSON** — Store benchmark summary snapshots you care to version (LME experiments, mode compares, “best so far” rows) as small **`*.json`** files in this folder. Prefer concise, reviewable files; regenerate after serious runs instead of committing every trial.

**Markdown (optional)** — Add milestone write-ups (scores, deltas vs a previous run, config notes) as needed. The CLI records metrics in the vault **`.metrics.jsonl`** and can optionally append to **`docs/memory/benchmarks/metrics/runs.jsonl`** when **`benchmark.append_repo_runs_jsonl`** is enabled in **`config.json`** — see [`docs/memory/benchmarks/metrics/README.md`](../metrics/README.md). This **`runs/`** directory is for narratives and JSON you want in git beside each other.

For how to run benchmarks and read scores, see **[`benchmarks/README.md`](../../../../benchmarks/README.md)** in the plugin repo root.
