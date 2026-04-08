---
description: Health-check the wiki — contradictions, orphans, gaps.
---

# Lint wiki

Follow the **wiki-lint** skill across `wiki/` and `wiki/index.md`. Propose concrete fixes or questions for the user.

## Quick usage

- Run after large merges: orphans, broken `[[wikilinks]]`, contradictions.

```bash
llm-wiki validate --wikilinks
```

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.
