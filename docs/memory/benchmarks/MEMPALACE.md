# Memory Palace / quotes suite (deferred)

**Peer benchmarks implemented in wiki-llm:** LongMemEval (LME), LoCoMo, and ConvoMem — see `bin/llm-wiki benchmark suites`, **`benchmarks/README.md`**, and **[comparisons.md](comparisons.md)**.

Those three match what **[MemPal / mempalace](https://github.com/milla-jovovich/mempalace)** publishes (their `benchmarks/BENCHMARKS.md`): same public datasets, not extra “missing” suites. wiki-llm runs them through **`benchmarks/lme_bench.py`** with vault search (`fts5`, `grep`, optional `chromadb` / `hybrid`).

### ConvoMem vs “ConvoDB”

There is **no** widely used retrieval benchmark named **ConvoDB** in MemPal’s docs. The Salesforce benchmark is **[ConvoMem](https://huggingface.co/datasets/Salesforce/ConvoMem)** (75k+ QA-style pairs). If you heard “ConvoDB,” it is almost certainly **ConvoMem** or informal wording — use **`benchmark run convomem --data …`** with LME-shaped JSON (full HF layout must be converted offline; see **`benchmarks/README.md`**).

### SQLite vs ChromaDB (not benchmarks)

**SQLite** here means **stdlib FTS5** (`benchmark.search.backend: fts5`) — a **search implementation**, not a dataset. MemPal’s story leans on **ChromaDB** embeddings for “raw” mode. wiki-llm can approximate that stack with **`chromadb`** or **`hybrid`** on the **same** LME / LoCoMo / ConvoMem tasks. Comparing systems is about **dataset + metric + split**, not about whether the index lives in SQLite or Chroma.

This **Memory Palace–native** benchmark (quotes / proprietary eval) is **explicitly deferred** until the upstream spec is vendored (see project plan).

When ready:

1. Clone or vendor the upstream **Memory Palace** evaluation code and dataset specification.
2. Define a **quotes** task format compatible with the wiki-llm vault layout (`raw/` → search → scoring).
3. Add a suite module under `benchmarks/`, wire `llm-wiki benchmark run mempalace`, and document expected metrics here.

Do not scrape third-party HTML for scores — use verified READMEs or papers (see [comparisons.md](comparisons.md)).
