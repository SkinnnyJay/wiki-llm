# wiki-llm benchmarks

Measure retrieval quality (recall@K, NDCG@K) for vault search backends and optional text compressors.

## Prerequisites

- Repo root on `PYTHONPATH` when importing (the `llm-wiki benchmark` CLI adds this).
- Python 3.10+ with `scripts/` dependencies (see project `README.md`).
- Optional: `chromadb` for semantic search (`pip install chromadb`).

## LME (LongMemEval-style)

The **LME** runner (`benchmarks/lme_bench.py`) downloads the public Hugging Face cleaned JSON (cached under `benchmark.data_cache_dir`, default `~/.cache/llm-wiki-benchmarks/lme_s_cleaned.json`) and evaluates **one haystack per question** against wiki-llm indexing.

### Retrieval pipeline (FTS5)

1. **Safe MATCH queries** — Questions go through `prepare_fts5_match_query()` in `scripts/lib/search.py` so punctuation such as `?` does not break FTS5 `MATCH` (which previously returned **zero** hits for many questions).
2. **Full shortlist** — `n_fetch` is at least the haystack size so the gold session is not truncated by `LIMIT`.
3. **One token pass per question** — Each bench markdown file is read once into `docs_tokens` for PRF mining and haystack TF×IDF (fast path).
4. **RRF fusion** — By default: duplicated OR BM25 list (`rrf_boost_or`, weights FTS), PRF-augmented search (16 terms from top-1 hit), haystack TF×IDF + question **bigram** bonus (weighted via `tfidf_rrf_weight`), optional **AND** query list (`and_rrf`), fused with reciprocal rank fusion. TF×IDF tokens use **head+tail** windows (`tfidf_head_tail`) so long sessions still contribute tail vocabulary. Optional **`or_late_rrf_weight`** re-fuses the merged list with a fresh OR BM25 ranking (tune toward 100% without dropping TF×IDF entirely).
5. **Heuristic ceiling** — On the public 500-question LME JSON, this stack reaches about **98% R@5** (on the order of **10** misses) without any neural rerank; the remainder are semantic / paraphrase gaps BM25+lexical cannot reliably fix.
6. **Optional LLM rerank (toward 100% R@5)** — Set `benchmark.search.rerank_llm.enabled` to true, **or** export `LLM_WIKI_BENCHMARK_LLM=1`. **`invoke`**: `anthropic_api` (default; needs `ANTHROPIC_API_KEY` or env from `.env`), **`claude_cli`** / **`codex_cli`** (local CLIs; prompt on stdin, default argv ends with `-`), or **`custom_cli`** with **`cli_argv`**. Haiku/API sees up to **80** documents per question, **head+tail** excerpts. Up to **five** doc indices, best first. ~**500** LLM calls for a full 500-question run. **MCP:** `wiki_benchmark_run` runs the same suites from an editor session (`use_llm`: true toggles the env flag for that run).

### CLI

```bash
# From repo root (or use absolute path to bin/llm-wiki)
python3 scripts/llm_wiki.py benchmark run lme --limit 10
python3 scripts/llm_wiki.py benchmark run longmemeval --backend fts5 --compress raw
python3 scripts/llm_wiki.py benchmark run lme --backend all --compress all --limit 50
python3 scripts/llm_wiki.py benchmark report --json
python3 scripts/llm_wiki.py benchmark history --limit 20
```

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

- **Failures:** `<vault>/.benchmarks/lme_failures.jsonl` (last matrix cell overwrites when using `--backend all --compress all`).
- **Metrics:** keys like `benchmark.lme.recall_at_5` in `.metrics.jsonl` when `metrics.enabled` is true and `benchmark.auto_record_metrics` is true.

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

Multi-hop conversational QA (target in product plan: high recall@10). The stub `benchmarks/locomo_bench.py` documents status; wire the official LoCoMo JSON and conversation → vault conversion when you add a local dataset path.

```bash
python3 scripts/llm_wiki.py benchmark run locomo --data /path/to/locomo.json
```

## ConvoMem

Large multi-category memory QA. Stub: `benchmarks/convomem_bench.py`.

```bash
python3 scripts/llm_wiki.py benchmark run convomem --data /path/to/convomem.json
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
```

Use `--limit 0` for the full 500-question set. Compare `recall_at_5` in printed JSON and in `benchmark report`.

## Iterative optimization loop

1. Run LME (or a `--limit` subset) and open `lme_failures.jsonl`.
2. Classify misses (vocabulary mismatch, dilution, chunking, ambiguity, etc.).
3. Flip one `benchmark.search.*` or `benchmark.chunking.*` toggle in `config.json` (hybrid, query expansion, rerank, LLM rerank, etc.).
4. Re-run the same command; compare `benchmark report` / `benchmark history`.
5. Keep changes that improve recall@K; revert if scores regress.

Targets from the product plan: **LME 100% R@5**, LoCoMo **99%+ R@10**, ConvoMem **99%+** average across categories — achieved by repeating the loop until metrics plateau, then optional LLM rerank for the last few misses.
