---
description: Answer from the wiki with citations; optionally file the answer back into wiki/.
---

# Query wiki

Follow the **wiki-query** skill: read `wiki/index.md`, open relevant pages, answer with inline citations. Offer to save notable answers under **wiki/** (durable) or **outputs/** (reports/drafts).

## Quick usage

- Ask a question about topics already in **`wiki/`** (not new web research — use **`/llm-wiki:research`** for that).

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.
