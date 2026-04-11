---
description: Build static graph viewer + wiki-data.json into llm-wiki/wiki/.og/
---

# Build static viewer

Run **`llm-wiki build-site`** (alias **`build-og`**) to emit `wiki/.og/` and **`wiki-data.json`**. Respects **`viewer.enabled`**.

## Quick usage

```bash
llm-wiki build-site
# Optional: build and serve over HTTP in one step (static assets need HTTP, not file://)
llm-wiki build-og --serve
# Or non-blocking (writes wiki/.og/.viewer-http.pid):
llm-wiki build-og --serve-background
# Stop the background server:
llm-wiki build-og --stop-serving
# Port: viewer.port in config, or override: --port 8765
```

Same behavior as **`./scripts/serve-viewer.sh`** after a build (that script only serves an existing `wiki/.og/`); it does not write the pid file used by **`--stop-serving`**.

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.
