---
description: List, search, save, or prune per-chat session memory under raw/memory/ (see wiki-session-memory).
---

# Session memory

Follow the **wiki-session-memory** skill. Prefer **CLI** over MCP when you have a shell (`skills/references/mcp-and-kg.md` § "CLI > MCP when local").

## Quick usage

- **Save notes for the current Claude session:** `llm-wiki memory save --current --summary "…" --tags "research,ingest"`
- **Search past sessions:** `llm-wiki memory recall "keywords" --limit 5`
- **List sessions:** `llm-wiki memory list --json`
- **Show one file:** `llm-wiki memory show --current` or `llm-wiki memory show SESSION_ID`
- **Prune:** `llm-wiki memory prune --keep 20` or `--older-than 30`

Hooks write **`llm-wiki/.current-session`** so `--current` resolves the chat session id without copying it.

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** From the vault root: `llm-wiki memory list` (empty ok if memory disabled).
- **Prompt:** Invoke **wiki-session-memory**; confirm `memory.enabled` in `llm-wiki/config.json` when using writes.

## See also

- **[`docs/ENV.md`](../docs/ENV.md)** — session memory, `max_sessions` auto-prune, recall vs search backend, privacy.
- **[`skills/references/mcp-and-kg.md`](../skills/references/mcp-and-kg.md)** — MCP tools and search backends.
