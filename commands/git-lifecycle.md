---
description: Audit vault git history by lifecycle phase (ingest, wiki, build, …) for flow progression.
---

# Vault git lifecycle

Audit vault commits by **phase** using subject prefixes from **`git.lifecycle.phases`** in **`config.json`**. See **WORKFLOWS.md** for phase tagging conventions.

## Quick usage

```bash
llm-wiki git lifecycle -n 40
llm-wiki git lifecycle --phase ingest -n 50
llm-wiki git lifecycle --json -n 100
llm-wiki git snapshot -m "merged HN notes" --phase wiki
```

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.
