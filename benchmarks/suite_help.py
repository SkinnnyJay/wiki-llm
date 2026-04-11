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

**Not implemented here:** Memory Palace’s **own** proprietary eval / quotes task (deferred until an upstream spec is vendored).

Full detail: **`benchmarks/README.md`**; optional tracked run notes: **`docs/memory/benchmarks/runs/README.md`**.
"""


def describe_benchmark_suites() -> str:
    return SUITES_MARKDOWN.strip() + "\n"
