# LME before / after — all models (2026-04-09)

**Dataset:** HF `lme_s_cleaned.json`, **`--limit 500`**, `fts5` + `raw`, default RRF fusion (`fuse_original_weight` 0.35) for LLM runs unless noted.

## Before (archived runs, same day)

| Label | Config | R@5 | Failures | P/R/M/L | Wall s | Notes |
|-------|--------|-----|----------|---------|--------|--------|
| Baseline | No LLM | 0.98 | 10 | 0/4/6/0 | 83.13 | [lme_mode_compare…json](lme_mode_compare_2026-04-09.json) |
| Haiku LLM always | `claude-3-5-haiku-20241022` | 0.98 | 10 | 0/4/6/0 | 178.06 | Same as baseline |
| Adaptive | Haiku + `invoke_when: adaptive` | 0.98 | 10 | 0/4/6/0 | 94.75 | 454 LLM skips |
| Haiku low fuse | fuse weight 0.15 | 0.98 | 10 | — | 173.3 | [follow-up…json](lme_followup_experiments_2026-04-09.json) |
| Haiku no fuse | `fuse_original_rrf: false` | 0.98 | 10 | — | 183.78 | |
| Sonnet 4.5 | `claude-sonnet-4-5-20250929` | 0.98 | 10 | — | 188.35 | |

## After (this session, fresh 500-Q runs)

| Run | Model / invoke | R@5 | Failures | P/R/M/L | Wall s | config_hash |
|-----|----------------|-----|----------|---------|--------|-------------|
| Baseline | — | 0.98 | 10 | 0/4/6/0 | 86.99 | `241f74d2550e` |
| Sonnet 4.6 | `claude-sonnet-4-6`, `anthropic_api` | 0.98 | 10 | 0/4/6/0 | 175.06 | `dfc1c6dac785` |
| Opus 4.6 | `claude-opus-4-6`, `anthropic_api` | 0.98 | 10 | 0/4/6/0 | 225.91 | `7cd607487cf6` |
| GPT-5.4 | `gpt-5.4`, `openai_api` | 0.98 | 10 | **0/0/0/10** | 121.39 | `a40b0fb51996` — **no key**; rerun below |

### GPT-5.4 with `OPENAI_API_KEY` (`.env.local`)

| Run | R@5 | Failures | P/R/M/L | Wall s | Notes |
|-----|-----|----------|---------|--------|--------|
| `openai_gpt_5_4` | **0.98** | 10 | **0/4/6/0** | **246.62** | `llm_invoked: true`; same aggregate as baseline/Sonnet/Opus; [partial JSON](lme_before_after_all_models_2026-04-09_partial_openai_gpt_5_4.json) |

### Earlier GPT-5.4 row (no key)

Without **`OPENAI_API_KEY`**, the harness had **`llm_can_run: false`**, **`llm_invoked: false`**, and misses bucketed **L** (not R/M). Re-run after setting the key:

`LME_ONLY=openai_gpt_5_4 LME_LIMIT=500 python3 scripts/.tmp/run_lme_all_models_report.py`

## Machine-readable bundle

- [lme_before_after_all_models_2026-04-09.json](lme_before_after_all_models_2026-04-09.json) — embeds **before_snapshots** + **after_runs_this_session**
