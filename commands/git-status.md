---
description: Vault-scoped git status (requires git.enabled in llm-wiki/config.json).
---

# Vault git status

Show **`git status`** for the vault only. If **`git.enabled`** is false, tell the user to enable it in **`llm-wiki/config.json`**.

## Quick usage

```bash
llm-wiki git status
```

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.
