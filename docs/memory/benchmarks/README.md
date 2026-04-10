# Memory × benchmarks

This folder holds **benchmark roadmap, comparisons, and (when implemented) run reports** for long-term retrieval evaluation — separate from per-vault wiki content. **“Memory” here means long-context / retrieval evaluation docs**, not the session-memory feature (`raw/memory/`).

## Roadmap status (high level)

| Phase | Focus |
|-------|--------|
| 1–2 | LME failure buckets, tune toward R@5 = 1.0 on 500 (see [`PLAN.md`](./PLAN.md)) |
| 3–4 | Markdown reports, [`comparisons.md`](./comparisons.md) (primary sources only) |
| 5 | LoCoMo & ConvoMem wiring after LME targets |
| 6 | Memory Palace / quotes suite — **deferred** ([`MEMPALACE.md`](./MEMPALACE.md)) |

Full detail: **[PLAN.md](./PLAN.md)**.

- **[PLAN.md](./PLAN.md)** — LME failure analysis, metrics strategy (vault `.metrics.jsonl` + optional repo `runs.jsonl`), reports, comparisons, phased work (LoCoMo, ConvoMem, deferred Memory Palace/quotes).
- **[comparisons.md](./comparisons.md)** — wiki-llm vs external systems: methodology (250 vs 500), measured rows, Memory Palace / leaderboards (with comparability caveats).
- **[why_rerank_doesnt_raise_lme.md](./why_rerank_doesnt_raise_lme.md)** — why stronger rerank models often don’t change aggregate R@5; fusion, excerpts, and **`OPENAI_API_KEY`** / bucket **L** troubleshooting.
- **[lme_misses_blocking_100.md](./lme_misses_blocking_100.md)** — baseline **10** misses (heuristic, R@5 ≈ 0.98) vs best validated LLM rerank (**1** miss, R@5 = 0.998); remaining **`gpt4_4929293b`** (bucket **M**). Pairs with **[`runs/rerank_cli_validated_2026-04-10.json`](./runs/rerank_cli_validated_2026-04-10.json)** and fixture **`tests/fixtures/lme_misses_best_run.json`** (guards drift in tracked `question_id`s).
- **[MEMPALACE.md](./MEMPALACE.md)** — placeholder for deferred Memory Palace / quotes suite.
- **[metrics/](./metrics/)** — optional `runs.jsonl` when `benchmark.append_repo_runs_jsonl` is enabled.
- **[runs/](./runs/)** — JSON snapshots and optional milestone Markdown; see **[runs/README.md](./runs/README.md)**.

**Iteration workflow (no code in this folder):** forward-only protocol, **`iterate_lme_rerank.py`**, and CLI flags live in repo root **[`benchmarks/README.md`](../../benchmarks/README.md)** (sections *Forward-only micro-optimization* and *Batch iteration + chart*).

Operational benchmark docs remain in the repo root **[`benchmarks/README.md`](../../benchmarks/README.md)**.
