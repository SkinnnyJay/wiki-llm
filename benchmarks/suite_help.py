"""Static help text for ``llm-wiki benchmark suites`` (Memory Palace peer benchmarks)."""

from __future__ import annotations

# Primary sources: LongMemEval paper/HF; snap-research/locomo; Salesforce ConvoMem HF.
SUITES_MARKDOWN = """\
# Retrieval benchmark suites (wiki-llm)

These are the **peer benchmarks** often cited next to systems like **Memory Palace**
(LongMemEval, LoCoMo, ConvoMem). wiki-llm implements all three via the same LME harness
(`benchmarks/lme_bench.py`).

| Suite | CLI | Dataset | Typical headline metric | Metrics keys |
|-------|-----|---------|-------------------------|--------------|
| **LongMemEval (LME)** | `benchmark run lme` | HF cleaned JSON (cached) | R@5 (500 Q) | `benchmark.lme.*` |
| **LoCoMo** | `benchmark run locomo` | `locomo10.json` ([snap-research/locomo](https://github.com/snap-research/locomo)) | R@10 (paper) | `benchmark.locomo.*` |
| **ConvoMem** | `benchmark run convomem --data …` | LME-shaped JSON (you convert / subset [Salesforce/ConvoMem](https://huggingface.co/datasets/Salesforce/ConvoMem)) | category-dependent | `benchmark.convomem.*` |

**Examples**

```bash
python3 scripts/llm_wiki.py benchmark run lme --limit 500 --backend fts5 --compress raw
python3 scripts/llm_wiki.py benchmark run locomo --limit 250
python3 scripts/llm_wiki.py benchmark run convomem --data benchmarks/fixtures/convomem_tiny.json
```

**Peer backends (optional, same LME JSON):** `benchmark run lme --peer mem0` (repeat `--peer` for several). Installs and vector data live under **`benchmark.peers.cache_dir`** (default `~/.cache/llm-wiki-benchmarks/peers`, not tracked in git). Peers: **mem0** (pip `mem0ai`), **mempalace** / **claude-mem** / **supermemory** (optional `MEMPALACE_BENCH_CMD` / `CLAUDE_MEM_BENCH_CMD` / `SUPERMEMORY_BENCH_CMD` JSON stdin→stdout bridges). Dimension scores (Data Integrity, Simplicity, Integration, Arch Maturity) merge **proxies** with **`benchmarks/peers/rubric_overrides.json`**.

**Not implemented here:** Memory Palace’s **own** proprietary eval / quotes task (deferred until an upstream spec is vendored).

Full detail: **`benchmarks/README.md`**; optional tracked run notes: **`docs/memory/benchmarks/runs/README.md`**.
"""


def describe_benchmark_suites() -> str:
    return SUITES_MARKDOWN.strip() + "\n"
