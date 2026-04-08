---
description: Ad-hoc research on a topic — discover sources, ingest into raw/, merge into wiki/, with stepped progress and logging (wiki-research skill).
---

# Research (ad-hoc)

Follow the **wiki-research** skill. This command is **topic-led**; for recurring batch fetches from **`research-tasks.json`**, use **`/llm-wiki:research-loop`** instead.

## Quick usage

```bash
llm-wiki integrations status
llm-wiki ingest …   # after the skill picks adapters/paths
```

## Arguments

**Topic / instructions:** $ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.
