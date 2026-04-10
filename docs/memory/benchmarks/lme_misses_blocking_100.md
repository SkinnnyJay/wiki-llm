# LME: what still blocks R@5 = 100%

Buckets (from `benchmarks/lme_bench.py`):

| Bucket | Meaning |
|--------|---------|
| **P** | Pool miss — gold session not in the retrieved candidate list at all |
| **R** | Rank miss — gold in pool but **session rank** after ordering lands **after top-5** |
| **M** | Multi-gold — more than one correct session; harder to satisfy |
| **L** | LLM/env — `LLM_WIKI_BENCHMARK_LLM=1` wanted rerank but backend could not run |

On the public **500-question** LME JSON, **heuristic-only** (no LLM rerank) tops out around **R@5 ≈ 0.98** (~**10** misses). See [`runs/rerank_cli_validated_2026-04-10.json`](runs/rerank_cli_validated_2026-04-10.json).

## Baseline (no LLM) — 10 misses at R@5 = 0.98

| `question_id` | Bucket | Notes |
|---------------|--------|--------|
| `gpt4_f2262a51` | M | Multiple gold sessions |
| `75832dbd` | R | Rank |
| `06f04340` | R | Rank |
| `d6233ab6` | R | Rank |
| `8e91e7d9` | M | Multi-gold |
| `gpt4_e061b84g` | M | Multi-gold |
| `gpt4_1e4a8aec` | M | Multi-gold |
| `gpt4_4929293b` | M | Multi-gold |
| `eac54add` | M | Multi-gold |
| `gpt4_8279ba03` | R | Rank |

## Best validated LLM rerank in-repo — **1** miss at R@5 = 0.998

Run: **`more_picks_fuse`** (Auto CLI, **12** `max_picks`, fusion on), same JSON file.

| `question_id` | Bucket | Question (short) |
|---------------|--------|------------------|
| `gpt4_4929293b` | M | What was the life event of one of my relatives that I participated in a week ago? |

**Gold sessions:** `answer_add9b013_1`, `answer_add9b013_2` — two valid sessions; retrieval must surface the right one **in the top-5 session slots** after rerank. This is the last known blocker for **100%** in that experiment.

## Other strong configs (still not 100%)

**`default_fuse`** (R@5 **0.994**, **3** misses): `195a1a1b`, `gpt4_4929293b`, `gpt4_8279ba03`.

---

Use the fixture [`tests/fixtures/lme_misses_best_run.json`](../../../tests/fixtures/lme_misses_best_run.json) for regression tracking. Re-run full LME after pipeline changes and update that file when the last miss is fixed.
