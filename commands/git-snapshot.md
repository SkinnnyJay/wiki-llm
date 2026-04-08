---
description: Commit current vault state with a message (vault-scoped git).
---

# Vault git snapshot

Commit the vault working tree with **`llm-wiki git snapshot`**. Use **`--phase`** for lifecycle tags (see **`/llm-wiki:git-lifecycle`**).

## Quick usage

```bash
llm-wiki git snapshot -m "YOUR_MESSAGE"
llm-wiki git snapshot -m "merged topics" --phase wiki
```

If `$ARGUMENTS` is non-empty, use it as the message.

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.
