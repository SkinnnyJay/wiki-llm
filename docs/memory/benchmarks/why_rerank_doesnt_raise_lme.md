# Why LLM rerank didn't raise LME R@5 (it was a bug)

> **Update 2026-04-10:** The original analysis below (items 1-7) was based on experiments where the **Anthropic API key was depleted**. Every API call silently failed and fell back to the original BM25 order. When tested with a **working API**, Sonnet and gpt-4o moved gold from rank [8, 11, 15] to **[0, 1, 2]** on a key miss question, and a partial 500-question run showed **R@5 = 0.994** (3 failures, down from 10). See [comparisons.md](comparisons.md) for the corrected results.
>
> **Bugs fixed:** (1) silent API error swallowing, (2) `_default_rerank_cli_argv` passing `-` as literal prompt, (3) no logging when rerank API calls fail. **Key insight:** RRF fusion is essential — without it, the LLM's top-5 picks may not include gold, and the gold stays at its BM25 rank.

On the public **500-question** LME slice, **heuristic retrieval already reaches ~98% R@5**. The remaining misses are usually **not** "the model is too dumb," but a combination of:

1. **Gold is in the pool, wrong order** — Failure logs show `gold_in_pool_pre_llm: true` and buckets **R** / **M** (rank vs multi-gold). The task is **session-level top-5** after mapping paths → sessions; the right file may sit at **position 6+** in that ordering.

2. **RRF fusion with retrieval** — Default `fuse_original_rrf` + `fuse_original_weight` **blends** the LLM's ordering with BM25/PRF. Even a "correct" LLM order is **pulled back** toward the original list, so **aggregate rank may not move enough** to flip R@5.

3. **Same fused order on misses** — In measured runs, **`llm_rerank_reordered` was often `false` on miss rows**: the **final path list matched the pre-LLM list** for those questions (LLM agreed with retrieval, parse fell back, or fusion reproduced the same order). Stronger models **cannot help** if the pipeline never applies a different order.

4. **Excerpt limits** — Rerank sees **head+tail** chunks (`max_chars` / `excerpt_mode`). If the decisive phrase is **outside** those windows, the model has no signal to promote the gold session. **Frontmatter was also not stripped**, wasting ~100-150 chars of the budget on YAML metadata (fixed).

5. **Paraphrase / time reasoning** — Some questions need **semantic** or **temporal** alignment that **lexical + short excerpts** don't surface; that's an **input / retrieval** problem, not only rerank.

6. **Only 5 picks returned** — `max_picks=5` meant the LLM's full ranking signal was discarded beyond its top 5 choices, leaving too little signal to survive fusion (now configurable).

7. **Path-level reranking, session-level eval** — The reranker worked on individual file paths, but LME evaluates at the session level. Multiple paths can map to the same session, adding noise (session dedup option now available).

**What would move the needle:** change **retrieval** (fusion weights, `n_fetch`, session/path ordering), **rerank inputs** (larger excerpts, different `max_candidates`), or **fusion off / lower weight** *with* full-500 regression checks — not only swapping Haiku → Sonnet → Opus with the same fused pipeline.

---

## Experiment knobs (config.json → `benchmark.search.rerank_llm`)

All experiments below modify **`benchmark.search.rerank_llm.*`** in config or override via env. Run each against the **full 500** to measure impact on the 10 miss questions:

```bash
LLM_WIKI_BENCHMARK_LLM=1 python3 scripts/llm_wiki.py benchmark run lme --limit 0
```

### Experiment A: Larger excerpts + fewer candidates

Default `max_chars=3600` with 80 candidates buries the decisive content. Try 10k chars with 25 candidates — prompt stays manageable, each document gets 4× more text.

```json
{ "max_chars": 10000, "max_candidates": 25, "fuse_original_rrf": false }
```

### Experiment B: More picks to survive fusion

Default `max_picks=5` gives the LLM almost no room to reorder. Try 10-15 so more ranking signal survives the RRF fusion step.

```json
{ "max_picks": 12, "fuse_original_weight": 0.15 }
```

### Experiment C: Session-level dedup

Merge all paths belonging to the same session into one "Document" block before sending to the LLM. Reduces noise and lets the reranker rank actual sessions.

```json
{ "session_dedup": true, "max_chars": 8000, "max_candidates": 30 }
```

### Experiment D: Local cross-encoder (no API calls)

Use a 435M-param cross-encoder (`mxbai-rerank-large-v1`) that sees full passages on CPU. ~650ms per query, deterministic, no API cost. Requires `pip install sentence-transformers`.

```json
{ "invoke": "cross_encoder", "cross_encoder_model": "mixedbread-ai/mxbai-rerank-large-v1", "max_chars": 10000, "max_picks": 10 }
```

### Experiment E: Combined (recommended first try)

Strip frontmatter (now automatic), large excerpts, session dedup, no fusion, more picks:

```json
{
  "enabled": true,
  "max_chars": 10000,
  "max_candidates": 25,
  "max_picks": 12,
  "fuse_original_rrf": false,
  "session_dedup": true,
  "invoke": "anthropic_api",
  "model": "claude-sonnet-4-6"
}
```

### Why MemPalace uses reranking (and it works for them)

MemPalace starts from a **lower baseline** (96.6% R@5 with ChromaDB semantic embeddings) with **different failure modes**: their misses are vocabulary-gap queries where embedding similarity ranks the gold session outside top-5. An LLM reranker reads actual text and promotes semantically relevant but lexically dissimilar passages — exactly the gap embeddings leave.

wiki-llm's BM25+PRF pipeline captures most of these at **98%**. With a working LLM reranker + RRF fusion, the partial run reached **0.994** (3 remaining misses). The earlier claim that the LLM "agrees with BM25" was wrong — the API was silently failing. When it works, Sonnet places all 3 gold sessions at ranks [0, 1, 2] for the tested miss question.

(MemPalace's claimed 100% uses 3 hand-coded question-specific patches; held-out = 98.4%.)

---

## OpenAI rerank: `llm_can_run` / bucket **L**

If **`OPENAI_API_KEY`** is missing or empty in the process environment, `invoke: openai_api` sets **`llm_can_run: false`**, **`llm_invoked: false`**, and misses can be bucketed **L** ("wanted LLM + env on + API not runnable") even though **R@5** still matches the no-LLM baseline.

**Fix:** Put the key in **`.env`** or **`.env.local`** at the **plugin repo root**, or `export OPENAI_API_KEY=...` before running. As of the env-loader tweak, an **empty** placeholder in the shell no longer blocks loading a non-empty value from `.env`.

Verify before a long run:

```bash
cd /path/to/wiki-llm
python3 -c "import sys; from pathlib import Path; sys.path.insert(0,'scripts'); from lib.env_loader import load_plugin_dotenv; from lib.paths import plugin_root; load_plugin_dotenv(plugin_root()); import os; print('OPENAI_API_KEY:', 'yes' if os.environ.get('OPENAI_API_KEY','').strip() else 'no')"
```

Then:

```bash
LME_ONLY=openai_gpt_5_4 LME_LIMIT=500 python3 scripts/.tmp/run_lme_all_models_report.py
```

Expect **`failure_bucket_counts`** with **R/M** (not all **L**) and **`llm_invoked: true`** on failure rows if rerank actually ran.
