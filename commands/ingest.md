---
description: Materialize sources into llm-wiki/raw/ then merge into the wiki per skills.
---

# Ingest and merge

Follow **wiki-ingest** (and **wiki-maintainer** as needed): use **`llm-wiki ingest`** to land files in **`raw/`**, then merge into **`wiki/`** with index + log updates. For messy HTML/PDF/OCR, use **wiki-raw-prepare** / **`llm-wiki raw finish`** first.

If **`knowledge_graph.auto_update_on_ingest`** is enabled, run `llm-wiki kg rebuild` after merging — see **`skills/references/mcp-and-kg.md`**.

## Quick usage

```bash
llm-wiki ingest --list
llm-wiki ingest url "https://example.com" --out clips/example.md
```

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.
