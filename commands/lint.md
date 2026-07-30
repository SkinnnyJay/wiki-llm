---
description: Health-check the wiki — orphans, links, claims, compile gates.
---

# Lint wiki

Follow the **wiki-lint** skill across `wiki/` and `wiki/index.md`. Prefer machine gates first, then semantic contradiction review.

## Quick usage

```bash
llm-wiki lint --write-report
llm-wiki compile --no-site
# surgical (pages citing one source):
llm-wiki compile --raw raw/path.md --no-site
llm-wiki knowledge-test --file examples/knowledge-tests.json
```

MCP (after `mcp.compile_enabled=true`): **`wiki_lint`**, **`wiki_compile`**, **`wiki_knowledge_test`**.

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.
