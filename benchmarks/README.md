# wiki-llm benchmarks

Measure retrieval quality (recall@K, NDCG@K) for vault search backends and optional text compressors.

## Metrics storage (where results go)

- **Primary:** Benchmark keys (`benchmark.lme.recall_at_5`, etc.) are written to the vault **`storage.metrics_db`** file (default **`llm-wiki/.metrics.jsonl`**) when `benchmark.auto_record_metrics` is true — same append-only JSONL as optional operational metrics (`search.*`, `mcp.*`, …), distinguished by **`key`** prefix.
- **Optional git-tracked mirror:** Set **`benchmark.append_repo_runs_jsonl`** to **`true`** in `config.json` to also append one line per run to **`docs/memory/benchmarks/metrics/runs.jsonl`** inside the **plugin** clone (for charts and CI). Default is **`false`** so normal runs do not dirty the repo. See [`docs/memory/benchmarks/metrics/README.md`](../docs/memory/benchmarks/metrics/README.md).

## Prerequisites

- Repo root on `PYTHONPATH` when importing (the `llm-wiki benchmark` CLI adds this).
- Python 3.10+ with `scripts/` dependencies (see project `README.md`).
- Optional: `chromadb` for semantic / hybrid search — install from repo root with **`pip install -r requirements-optional.txt`** (version range pinned there; avoids surprise on-disk breaks across major Chroma releases).

## LME (LongMemEval-style)

The **LME** runner (`benchmarks/lme_bench.py`) downloads the public Hugging Face cleaned JSON (cached under `benchmark.data_cache_dir`, default `~/.cache/llm-wiki-benchmarks/lme_s_cleaned.json`) and evaluates **one haystack per question** against wiki-llm indexing.

### Retrieval pipeline (FTS5)

1. **Safe MATCH queries** — Questions go through `prepare_fts5_match_query()` in `scripts/lib/search.py` so punctuation such as `?` does not break FTS5 `MATCH` (which previously returned **zero** hits for many questions).
2. **Full shortlist** — `n_fetch` is at least the haystack size so the gold session is not truncated by `LIMIT`.
3. **One token pass per question** — Each bench markdown file is read once into `docs_tokens` for PRF mining and haystack TF×IDF (fast path).
4. **RRF fusion** — By default: duplicated OR BM25 list (`rrf_boost_or`, weights FTS), PRF-augmented search (16 terms from top-1 hit), haystack TF×IDF + question **bigram** bonus (weighted via `tfidf_rrf_weight`), optional **AND** query list (`and_rrf`), fused with reciprocal rank fusion. TF×IDF tokens use **head+tail** windows (`tfidf_head_tail`) so long sessions still contribute tail vocabulary. Optional **`or_late_rrf_weight`** re-fuses the merged list with a fresh OR BM25 ranking. Default in `config_loader` is **0.15** (helps late-BM25 recall without dropping TF×IDF entirely).
5. **Heuristic ceiling** — On the public 500-question LME JSON, this stack reaches about **98% R@5** (on the order of **10** misses) without any neural rerank; the remainder are semantic / paraphrase gaps BM25+lexical cannot reliably fix.
   - **What those misses are (typical full run):** `lme_failures.jsonl` shows **`gold_in_pool_pre_llm: true`** for each — the gold session’s file is in the candidate path list, but its **session rank** lands **after position 5** once paths are mapped to session order (so **P pool-miss count is 0**; buckets are mostly **R** rank vs **M** multi-gold). Turning on **`rerank_enabled`** / **`lexical_rrf`** / **`refine_head_lexical`** can **hurt** aggregate R@5 badly in testing; do not enable globally without re-measuring on 500.
   - **Chasing 0 misses:** use **LLM rerank** (below) on the shortlist, or accept the heuristic ceiling.
6. **Optional LLM rerank (toward 100% R@5)** — Set `benchmark.search.rerank_llm.enabled` to true, **or** export `LLM_WIKI_BENCHMARK_LLM=1`. **`invoke`**: **`anthropic_api`** (default; `ANTHROPIC_API_KEY` / `api_key_env`), **`openai_api`** (`OPENAI_API_KEY`; set `model` to e.g. **`gpt-5.4`**), **`claude_cli`** / **`codex_cli`**, or **`custom_cli`**. Default **`model`** is **`claude-sonnet-4-6`**. Other API IDs (see provider docs): **`claude-opus-4-6`**, **`gpt-5.4`** or **`gpt-5.4-2026-03-05`**. Up to **80** documents per question, **head+tail** excerpts; up to **five** doc indices, best first. ~**500** LLM calls for a full 500-question run. **MCP:** `wiki_benchmark_run` runs the same suites from an editor session (`use_llm`: true toggles the env flag for that run).
   - **Fusion (default on):** `fuse_original_rrf` (default **true**) blends the LLM’s ordering with the pre-LLM retrieval order via weighted RRF (`fuse_original_weight`, default **0.35**) so a bad rerank pass does not wipe out strong BM25/PRF hits. Set `fuse_original_rrf` to **false** to use the LLM order only.
   - **Adaptive LLM calls:** `invoke_when`: **always** (default) or **adaptive** — cheap lexical scores on the top `adaptive_head` paths vs a `adaptive_lookback` tail window; skips the LLM when the head looks strong and the tail is not competitive (fewer API calls; intended to avoid regressions on easy questions). Summary includes **`llm_adaptive_skips`** and **`llm_adaptive_confidence_mean`** (mean of `compute_rerank_confidence` scores on adaptive runs). **`adaptive_confidence_threshold`** (default **0.5**) — skip LLM when confidence ≥ threshold (higher = more skips). Tune `adaptive_tail_margin`, `adaptive_min_head_lex`, `adaptive_max_chars`.
   - **Parallel LLM rerank:** `parallel_workers` (default **1**) — when **> 1**, LME defers LLM rerank to a thread pool after retrieval (each question uses a separate vault under `.benchmark_run/q_<idx>/` so vaults stay concurrent-safe). Combine with **`rerank_llm.enabled`** / `LLM_WIKI_BENCHMARK_LLM=1`. Typical **4–8** workers for wall-clock speedup on CLI/API rerank.
   - **Persistent Claude CLI pool:** `persistent_cli_pool` (default **false**), **`persistent_pool_size`** (default **4**) — keep a long-lived **`claude`** stream-json session per pool worker (Unix/macOS); falls back to one-shot `claude --print` on Windows or when the stream fails. Only applies to **`claude_cli`** / **`invoke: auto`** when Claude is selected.

### Forward-only micro-optimization (LME + LLM rerank)

Tune **one knob per experiment** and **merge only if quality does not regress** (use data, not intuition):

1. **Baseline** — Save summary JSON + miss `question_id`s (from `lme_failures.jsonl` or a tracked run under `docs/memory/benchmarks/runs/`). Use **`--limit 250`** for faster iteration; **confirm** headline numbers on full **500** (`--limit 0`).
2. **Gate** — Keep the change if **`recall_at_5` ≥ baseline** and **`failures` ≤ baseline**. If optimizing wall time, also require **`elapsed_s`** (or measured wall) not worse unless quality improved. Otherwise **revert**.
3. **Record** — Document the run (path, config hash, key knobs). With **`benchmark.append_repo_runs_jsonl`** enabled, use **`python3 scripts/llm_wiki.py benchmark compare`** for last-two snapshots.

**Knobs worth trying next (usually one at a time):** `fuse_original_weight` (lower → trust LLM order more; raise if R@5 drops), `max_picks` / `max_candidates`, `max_chars` / `excerpt_mode`, `invoke_when: adaptive` + `adaptive_confidence_threshold` (fewer LLM calls; validate R@5 on 500), `parallel_workers` (throughput only; should not change R@5).

### Batch iteration + chart (150 trials)

[`benchmarks/iterate_lme_rerank.py`](iterate_lme_rerank.py) runs a **deterministic schedule** of `rerank_llm` micro-knobs (fuse weight, `max_picks`, `max_chars`, `always` vs `adaptive` + threshold), logs **JSONL + CSV**, writes **`iteration_lme_rerank_<timestamp>_best.json`**, and an **HTML** report with **Chart.js** (R@5 and failures vs iteration). Requires **`LLM_WIKI_BENCHMARK_LLM=1`** and a working CLI/API.

```bash
# Preview schedule (no benchmark runs)
python3 benchmarks/iterate_lme_rerank.py --dry-run --iterations 150

# Example: 150 trials × 50 questions (faster); confirm on --limit 0 separately
LLM_WIKI_BENCHMARK_LLM=1 python3 benchmarks/iterate_lme_rerank.py --iterations 150 --limit 50 \\
  --out-dir docs/memory/benchmarks/runs
```

Open the generated **`iteration_lme_rerank_*.html`** in a browser for charts. Rows with **`best_so_far: true`** in JSONL mark a new rolling best (higher R@5, then fewer failures).

**See also:** optional tracked run artifacts under [`docs/memory/benchmarks/runs/`](../docs/memory/benchmarks/runs/README.md); failure analysis lives in generated **`lme_failures.jsonl`** (per run) and **`benchmark report`** output.

### Eval size (`--limit`)

| `--limit` | Typical use |
|-----------|-------------|
| `10`–`50` | Quick sanity / CI-style smoke |
| **`250`** | **Mid eval** — ~half the LME JSON cost of 500; still uses **prefix order** (first N questions), not random sampling |
| `0` | **Full** LME set (**500** questions on the default HF cleaned JSON) — headline number |

A **250-slice** estimates the full score but has **higher variance** than 500. **Confirm** important claims on **`--limit 0`**. LoCoMo / ConvoMem: `--limit` caps the number of QA rows after conversion (`benchmark run locomo --limit 250`).

### List suites (Memory Palace peers)

```bash
python3 scripts/llm_wiki.py benchmark suites
```

Prints a short table of **LongMemEval (LME)**, **LoCoMo**, and **ConvoMem** with CLI names, metric keys, and example commands. Same text lives in `benchmarks/suite_help.py`.

### CLI

```bash
# From repo root (or use absolute path to bin/llm-wiki)
python3 scripts/llm_wiki.py benchmark run lme --limit 10
python3 scripts/llm_wiki.py benchmark run longmemeval --backend fts5 --compress raw
python3 scripts/llm_wiki.py benchmark run lme --backend all --compress all --limit 50
python3 scripts/llm_wiki.py benchmark report --json
python3 scripts/llm_wiki.py benchmark history --limit 20
python3 scripts/llm_wiki.py benchmark compare
python3 scripts/llm_wiki.py benchmark analyze
python3 scripts/llm_wiki.py benchmark analyze --json
```

`benchmark compare` diffs two recent `benchmark.lme.recall_at_5` snapshots (indices `--a` / `--b`, default last two).

`benchmark analyze` (default `--suite lme`) prints bucket counts, **`question_id`** list, and one line per miss (from `<vault>/.benchmarks/lme_failures.jsonl`). Use **`--failures PATH`** to read a saved JSONL; **`--json`** for machine-readable output (includes full rows). Works even when `benchmark.enabled` is false (read-only).

**After a missy run:** use the printed `question_id` values to spot-check retrieval order, then try **`benchmark.search.rerank_llm.model`** (e.g. a stronger Claude snapshot), **`fuse_original_weight`** (lower → trust LLM order more; raise if R@5 drops), or **`max_chars`** / **`excerpt_mode`** — re-measure full **500** after each change.

**Measured follow-up (2026-04-09, N=500):** Haiku with **fuse 0.15**, Haiku with **`fuse_original_rrf: false`**, and **Sonnet 4.5** with default fusion all stayed at **0.98 R@5 / 10 failures** vs heuristic. Failure rows showed **`llm_rerank_reordered: false`** on every miss — the merged order did not change vs pre-LLM for those questions. See **`docs/memory/benchmarks/runs/lme_followup_experiments_2026-04-09.json`** and **`benchmark analyze --failures …`** on **`docs/memory/benchmarks/runs/lme_failures_sonnet_fuse_default.jsonl`**.

Aliases: `lme` and `longmemeval` are the same suite.

### Backends

| Name       | Notes                                      |
|-----------|---------------------------------------------|
| `fts5`    | SQLite FTS5 BM25 (default)                  |
| `grep`    | Line-oriented grep fallback               |
| `chromadb`| Embeddings (requires `chromadb`)          |
| `hybrid`  | FTS5 + Chroma fusion (see `bench_harness`) |
| `all`     | Runs `fts5`, `grep`, `chromadb`, `hybrid`  |

### Compressors

`raw`, `steno`, `prune`, `extract`, `compact`, or `all` (runs all five). Implemented in `scripts/lib/compressors.py`.

### Outputs

- **Failures:** `<vault>/.benchmarks/lme_failures.jsonl` (last matrix cell overwrites when using `--backend all --compress all`). Each miss includes **`failure_bucket`**: `P` (pool), `R` (rank), `M` (multi-gold), `L` (LLM/env off when `LLM_WIKI_BENCHMARK_LLM=1`), plus `gold_in_pool_pre_llm`, `llm_invoked`, etc.
- **Metrics:** keys like `benchmark.lme.recall_at_5` in `.metrics.jsonl` when `metrics.enabled` is true and `benchmark.auto_record_metrics` is true. Record **meta** includes `config_hash`, `limit`, `llm_flag`, `rerank_invoke`, `git_sha`, and `failure_bucket_counts` when present.
- **Optional:** `benchmark.write_run_sidecar` (default true) writes JSON under `.benchmarks/runs/`. Set **`benchmark.append_repo_runs_jsonl`** true to append chart-friendly lines to `docs/memory/benchmarks/metrics/runs.jsonl` in the plugin repo.
- **Debug rerank:** `benchmark.debug_rerank` in config or `LLM_WIKI_BENCHMARK_DEBUG_RERANK=1` logs one stderr line per question when LLM rerank runs.

### Config

See `benchmark` in `scripts/lib/config_loader.py` `DEFAULTS` and your vault `config.json`. Important keys:

- `benchmark.enabled` — gate the CLI.
- `benchmark.search.backend` — default backend when `--backend` is omitted.
- `benchmark.compress_method` — default compressor.
- `benchmark.search.rerank_llm` — optional rerank (`invoke`: `anthropic_api` | `claude_cli` | …).

### Optional rerank smoke tests

Integration checks for API vs local `claude` CLI (tiny two-doc vault):

```bash
RUN_RERANK_SMOKE=1 python3 -m pytest tests/test_rerank_llm_smoke.py -v
```

API test needs `ANTHROPIC_API_KEY` (or `.env`); CLI test needs `claude` on `PATH`. Without `RUN_RERANK_SMOKE=1`, those tests are skipped so CI stays offline.

## LoCoMo

Multi-hop conversational QA. The runner downloads **`locomo10.json`** from [snap-research/locomo](https://github.com/snap-research/locomo) (cache: `benchmark.data_cache_dir`) unless you pass **`--data`**. Conversations are converted to the same LME-shaped haystack as LongMemEval, with gold sessions derived from evidence ids (`D18:5` → session `S18`). Metrics are recorded under **`benchmark.locomo.*`**.

```bash
python3 scripts/llm_wiki.py benchmark run locomo --limit 50
python3 scripts/llm_wiki.py benchmark run locomo --data /path/to/locomo10.json
```

## ConvoMem

Large multi-category memory QA (Salesforce/HF). Pass a JSON **array of LME-shaped entries** (same keys as LME: `haystack_sessions`, `haystack_session_ids`, `haystack_dates`, `question`, `answer_session_ids`). Subset or convert from the official dataset offline. Metrics: **`benchmark.convomem.*`**.

```bash
python3 scripts/llm_wiki.py benchmark run convomem --data /path/to/lme-shaped.json
# Tiny checked-in sample (CI / smoke):
python3 scripts/llm_wiki.py benchmark run convomem --data benchmarks/fixtures/convomem_tiny.json
```

## Scoring

Shared math lives in `benchmarks/bench_harness.py`:

- **Recall@K:** binary — 1 if any gold session index appears in the top-K ranked corpus indices, else 0.
- **NDCG@K:** standard DCG with binary relevance vs ideal.

Session order is derived from search result paths mapped back to `session_id` frontmatter.

## Baseline run (matrix)

Record starting scores before tuning:

```bash
python3 scripts/llm_wiki.py benchmark run lme --backend all --compress raw --limit 500
python3 scripts/llm_wiki.py benchmark run lme --limit 250
```

Use `--limit 0` for the full 500-question set. Compare `recall_at_5` in printed JSON and in `benchmark report`. For **leaderboard-style** comparisons vs other systems, add a short markdown note under **`docs/memory/benchmarks/runs/`** (or your team’s doc) with slice size, config, and caveats.

## Iterative optimization loop

1. Run LME (or a `--limit` subset) and open `lme_failures.jsonl`.
2. Classify misses (vocabulary mismatch, dilution, chunking, ambiguity, etc.).
3. Flip one `benchmark.search.*` or `benchmark.chunking.*` toggle in `config.json` (hybrid, query expansion, rerank, LLM rerank, etc.).
4. Re-run the same command; compare `benchmark report` / `benchmark history`.
5. Keep changes that improve recall@K; revert if scores regress.

Targets from the product plan: **LME 100% R@5**, LoCoMo **99%+ R@10**, ConvoMem **99%+** average across categories — achieved by repeating the loop until metrics plateau, then optional LLM rerank for the last few misses.
