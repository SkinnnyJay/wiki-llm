---
description: Generate a knowledge/cluster graph — pages colored by undirected link component (relational clusters).
---

# Knowledge graph (wikilink clusters)

Same pipeline as **`/llm-wiki:graph`**, but uses **connected components** of the wikilink graph: pages that reach each other through links share a color. Isolated pages are their own cluster.

> **Note:** This visualizes **wikilink topology**. For the **entity knowledge graph** (structured triples), use `llm-wiki kg` — see **`skills/references/mcp-and-kg.md`** § "Disambiguation".

## Quick usage

```bash
llm-wiki graph --mode knowledge
./scripts/serve-graph.sh
```

Use the sidebar legend for cluster size and sample titles. **wiki-lint** can suggest cross-links to merge small clusters.

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.
