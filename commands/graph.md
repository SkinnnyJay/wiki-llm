---
description: Generate an on-demand D3 link graph of llm-wiki/wiki into .tmp/llm-wiki-graph (GitHub-dark styled).
---

# Link graph

Follow **wiki-pipeline** (validate stage) indirectly — graphs are built from **`wiki/`** wikilinks. Run the CLI from the project root (vault discoverable via `./llm-wiki` or `LLM_WIKI_VAULT`).

## Quick usage

```bash
llm-wiki graph
./scripts/serve-graph.sh
```

Open `http://127.0.0.1:$PORT/` — **links** mode: node size ∝ degree, color ∝ connectivity. Optional: `--out /other/dir`.

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.
