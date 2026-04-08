---
description: Show vault git diff (working tree or staged).
---

# Vault git diff

Vault-scoped **git diff** (not the parent repo). Requires **`git.enabled`** and an initialized vault repository.

## Quick usage

```bash
llm-wiki git diff
llm-wiki git diff --staged
```

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.
