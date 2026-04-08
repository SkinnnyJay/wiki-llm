---
description: Validate and clean raw/ markdown; log preparation; optional vault git [prepare] commit.
---

# Raw prepare

Follow the **wiki-raw-prepare** skill: LLM cleanup if needed, then **`llm-wiki raw validate`** / **`raw finish`** and merge to **wiki** via **wiki-ingest** when ready.

## Quick usage

```bash
llm-wiki raw validate path/to/file.md --autofix
llm-wiki raw finish path/to/file.md -m "describe changes"
```

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.
