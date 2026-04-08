---
description: Run recurring research tasks from research-tasks.json / research-tasks.yaml (wiki-research-loop skill).
---

# Research loop (batch)

Follow the **wiki-research-loop** skill. Requires **`research_loop.enabled: true`**. Not the same as ad-hoc **`/llm-wiki:research`**.

## Quick usage

```bash
llm-wiki research-loop --dry-run
llm-wiki research-loop
```

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.
