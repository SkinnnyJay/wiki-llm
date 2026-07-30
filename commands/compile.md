---
description: Run knowledge CI gates after wiki merge (lint, claims, KG conflicts).
---

# Compile knowledge

Run the knowledge compiler after **wiki-ingest** / topic merges. Gates only — does **not** auto-write `wiki/` topic pages.

## Quick usage

```bash
llm-wiki compile --no-site
llm-wiki compile --schema --no-site
llm-wiki compile --raw raw/foo.md --no-site
llm-wiki compile --stubs --no-site   # drafts under outputs/stubs/ only
llm-wiki knowledge-test --file examples/knowledge-tests.json
```

MCP: set **`mcp.compile_enabled=true`** then **`wiki_compile`** (site rebuild also needs **`mcp.compile_allow_site`**).

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** `llm-wiki compile --no-site` on a configured vault; expect OK or a concrete lint/KG failure.
- **Prompt:** After a wiki merge, ask to compile; confirm `outputs/lint-report.json` exists.
