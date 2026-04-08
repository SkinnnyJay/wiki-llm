---
description: Build static graph viewer + wiki-data.json into llm-wiki/wiki/.og/
---

# Build static viewer

Run **`llm-wiki build-site`** (alias **`build-og`**) to emit `wiki/.og/` and **`wiki-data.json`**. Respects **`viewer.enabled`**.

## Quick usage

```bash
llm-wiki build-site
./scripts/serve-viewer.sh
```

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.
