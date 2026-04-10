# External benchmark comparisons

Tables for **published** systems vs **wiki-llm** runs. **Do not copy numbers from scraped HTML** — use papers, official READMEs, or Hugging Face dataset cards.

## How wiki-llm scores are produced

- **CLI:** `python3 scripts/llm_wiki.py benchmark run <suite> --limit N` from repo root (see [benchmarks/README.md](../../../benchmarks/README.md)).
- **`--limit`:** Uses the **first N items** in the dataset JSON (fixed order). It is **not** a random subsample — the first 250 and the full 500 can differ slightly in difficulty mix.
- **250 vs 500:** A **500-question** LME run is the headline "full LongMemEval-cleaned" eval. **250** is a cheaper mid-run (~half the time) with **higher variance** than 500; use it for iteration, then confirm on **500** before claiming a final number.
- **LLM rerank:** Heuristic-only vs `rerank_llm` + `LLM_WIKI_BENCHMARK_LLM=1` are different rows — note which you ran.

## wiki-llm measured rows (fill / refresh after each serious run)

| Suite | Config slice | Metric | Score | Failures | Notes |
|-------|----------------|--------|-------|----------|--------|
| **LME** | `lme`, fts5+raw, heuristic, `--limit 250` | R@5 | **0.98** | 5 | Prefix slice; config_hash `ed07345288f4` (example run) |
| **LME** | `lme`, fts5+raw, heuristic, `--limit 500` | R@5 | **0.98** | 10 | Full cleaned JSON; buckets R=4, M=6, P=0; `config_hash` `ea3ea6e64e50` (2026-04-09) |
| **LME** | same + `rerank_llm` Haiku API, `invoke_when: always`, fusion on | R@5 | **0.98** | 10 | Same failures as heuristic; `625a40067745`; ~178s wall |
| **LME** | same + `invoke_when: adaptive` (454 LLM skips, ~46 calls) | R@5 | **0.98** | 10 | No R@5 regression vs baseline; ~95s wall; `3b391fa3a14e` |
| **LoCoMo** | `locomo`, fts5+raw, `--limit 250` | R@5 / R@10 | **0.912** / **0.984** | 22 | `locomo10.json` → LME harness; primary paper metric is often R@10 |
| **ConvoMem** | `convomem` + `--data` (LME-shaped JSON) | — | — | — | Run when you have a converted slice |

Snapshot JSON: [runs/lme_mode_compare_2026-04-09.json](runs/lme_mode_compare_2026-04-09.json) (baseline vs LLM always vs adaptive, **N=500**).

Update this table when you change defaults or re-run on a release machine.

**Gap to R@5 = 1.0 on the full 500:** tracked miss lists and the last known **`gpt4_4929293b`** blocker are documented in **[lme_misses_blocking_100.md](lme_misses_blocking_100.md)** (pairs with **[runs/rerank_cli_validated_2026-04-10.json](runs/rerank_cli_validated_2026-04-10.json)**).

## Other systems (primary sources only)

| System / paper | Benchmark | Metric | Score | Primary source | Comparability |
|----------------|-----------|--------|-------|----------------|---------------|
| Memory Palace | (their tasks) | — | — | Official paper / repo when you run their eval | **Not** the same as LME R@5; add a row only after matching task + split |
| LoCoMo (reference) | LoCoMo | R@10 (etc.) | See paper | [snap-research.github.io/locomo](https://snap-research.github.io/locomo/) | Same `locomo10.json` family if you cite their split |
| ConvoMem | ConvoMem | Category metrics | See HF | [Salesforce/ConvoMem](https://huggingface.co/datasets/Salesforce/ConvoMem) | wiki-llm needs LME-shaped conversion for apples-to-apples retrieval |
| LongMemEval paper | LongMemEval | Task-dependent | See paper | [HF paper 2410.10813](https://huggingface.co/papers/2410.10813) | End-to-end QA vs our **retrieval R@K** may differ |

## Leaderboards (interpret carefully)

Third-party sites that quote "LongMemEval %" often report **full-system accuracy**, not **retrieval-only R@5** on the cleaned JSON. When comparing to **Memory Palace** or others, align **benchmark name, metric, and split** before claiming rank.

## Methodology notes

- **Same vault pipeline:** LME, LoCoMo (converted), and ConvoMem (LME-shaped) share `benchmarks/lme_bench.py` retrieval, fusion, optional LLM rerank (`config.json`).
- **Session memory** does not write benchmark metrics; see [PLAN.md](PLAN.md).

## Next steps (LME misses)

Measured **2026-04-09:** Haiku + default RRF fusion matched heuristic **R@5** on **N=500** (10 misses unchanged). To iterate:

1. **`benchmark analyze`** (LME failures log) — stable **`question_id`** list and P/R/M/L buckets from `lme_failures.jsonl`.
2. **Rerank experiments** (one knob per full-500 run): stronger **`rerank_llm.model`**, lower **`fuse_original_weight`** (trust LLM order more), larger **`max_chars`**, or **`fuse_original_rrf: false`** for an A/B.
3. **Cost** — **`invoke_when: adaptive`** preserved **0.98** with ~**91%** fewer LLM calls in that run; keep for routine checks once tuned.

### Follow-up experiments (2026-04-09, N=500, all LLM-always)

| Experiment | Model | Fusion | R@5 | Failures | Wall ≈ |
|------------|-------|--------|-----|----------|--------|
| Haiku low fuse | `claude-3-5-haiku-20241022` | RRF, weight **0.15** | **0.98** | 10 | ~173s |
| Haiku LLM-only order | Haiku | **`fuse_original_rrf: false`** | **0.98** | 10 | ~184s |
| Sonnet default fuse | **`claude-sonnet-4-5-20250929`** | RRF, weight 0.35 | **0.98** | 10 | ~188s |

**Outcome:** No change vs heuristic on aggregate. On the 10 misses (see [runs/lme_failures_sonnet_fuse_default.jsonl](runs/lme_failures_sonnet_fuse_default.jsonl)), **`llm_rerank_reordered` was false** for every row — final ordering matched pre-LLM paths, so the bottleneck is not "fusion too strong" alone; the reranker is **not producing a different winning order** than retrieval for these questions (or the API path returns a no-op order).

Snapshot: [runs/lme_followup_experiments_2026-04-09.json](runs/lme_followup_experiments_2026-04-09.json).

### Rerank input experiments — INVALIDATED (2026-04-09 → 2026-04-10)

> **Critical finding (2026-04-10):** All experiments below from 2026-04-09 were **invalid** — the Anthropic API key was depleted (`"Credit balance is too low"`). Every API call **silently failed** and fell back to the original BM25 order, producing identical baseline numbers. This was masked by three bugs:
>
> 1. **Silent error swallowing** — `except` blocks in `_rerank_paths_llm_*` returned `None` without logging; `_maybe_fuse(None)` returned the original paths unchanged. **Fixed:** now prints `[rerank] ... API error: ...` to stderr.
> 2. **`_default_rerank_cli_argv` bug** — `["claude", "-p", "-"]` passed `-` as the literal prompt argument, ignoring stdin entirely. **Fixed:** `["claude", "--print", "--tools", "", "--no-session-persistence"]`.
> 3. **Billing confusion** — Claude CLI uses the same Anthropic billing as the API key; it is NOT unlimited. The CLI returned `"Credit balance is too low"` with returncode 1.

The original table is preserved below for the record, but **all `reordered_on_miss=0` values were artifacts of silent API failure, not real LLM behavior.**

<details><summary>Original (invalid) table — 2026-04-09</summary>

| Experiment | Config delta | R@5 | Failures | Reord | Wall |
|------------|-------------|-----|----------|-------|------|
| Baseline (heuristic) | — | **0.98** | 10 | — | 92s |
| Haiku default fuse | `chars=3600, cand=80, fuse=0.35` | **0.98** | 10 | **0** | 186s |
| A: large excerpts | `chars=10000, cand=25, fuse=off` | **0.98** | 10 | **0** | 186s |
| B: more picks | `picks=12, fuse=0.15` | **0.98** | 10 | **0** | 180s |
| C: session dedup | `dedup, chars=8000, cand=30` | **0.98** | 10 | **0** | 187s |
| E: combined (Haiku) | `10k, dedup, 12 picks, no fuse` | **0.98** | 10 | **0** | 183s |
| E+Sonnet 4.6 | same + `claude-sonnet-4-6` | **0.98** | 10 | **0** | 186s |

</details>

### Single-question diagnostics (2026-04-10, working API confirmed)

Before API credits were exhausted, single-question tests on miss `gpt4_f2262a51` ("How many different doctors did I visit?") confirmed the reranker **absolutely works** when the API is functioning:

| Model | Invoke | Gold ranks before | Gold ranks after | Picks |
|-------|--------|------------------|-----------------|-------|
| gpt-4o-mini | `openai_api` | [8, 11, 15] | [0, 15, 19] | 1 of 3 gold in top-5 |
| **gpt-4o** | `openai_api` | [8, 11, 15] | **[0, 1, 2]** | **All 3 gold = perfect** |
| **Sonnet** | `claude_cli` | [8, 11, 15] | **[0, 1, 2]** | **All 3 gold = perfect** |

### Partial full run (Sonnet CLI, credits expired mid-run)

One 500-question run completed before credits fully depleted, showing **R@5=0.994, 3 failures** (rescued 7/10). This was **not reproducible** in a subsequent run (credits fully gone by then; all calls returned `"Credit balance is too low"`, falling back to baseline 0.98). The partial result is directionally valid but needs confirmation with working API credits.

| Config | R@5 | R@10 | Failures | Reord on miss | Wall |
|--------|-----|------|----------|---------------|------|
| Baseline (heuristic) | 0.98 | 0.988 | 10 | 0 | 93s |
| Sonnet CLI + default fuse (partial) | **0.994** | **1.000** | **3** | 2 | 1974s |
| A: 10k, 25 cand, no fuse | 0.98 | 0.988 | 10 | 0 | 1484s |
| Sonnet combined (no fuse) | 0.98 | 0.988 | 10 | 0 | 1351s |

The "no fuse" variants show 0.98 even when the API was partially working — without RRF fusion, the LLM's top-5 picks don't always include gold, leaving it at its original BM25 position.

**Conclusion (revised):** LLM reranking **works** — but only when (a) the API is actually responding and (b) **RRF fusion** is enabled to blend the LLM signal with BM25. Previous "dead end" conclusion was wrong; it was based on silently failed API calls. **To get definitive numbers: top up Anthropic or OpenAI credits and re-run.**

**Remaining 3 hard misses** (from partial run): `gpt4_f2262a51`, `gpt4_4929293b`, `gpt4_8279ba03`. These may be the true BM25+LLM ceiling, or may yield to larger candidate pools / different fusion weights.

Snapshots: [runs/rerank_experiments_cli_2026-04-09.json](runs/rerank_experiments_cli_2026-04-09.json), [runs/rerank_fuse_variants_2026-04-10.json](runs/rerank_fuse_variants_2026-04-10.json).
