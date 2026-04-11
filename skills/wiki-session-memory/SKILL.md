---
name: wiki-session-memory
description: Per-chat session memory in raw/memory/ — save, recall, list, prune. Use when the user wants continuity across Claude sessions or to audit past work.
---

# Wiki session memory

Stores one markdown file per chat session: **`raw/memory/<session-id>.md`**. Optional feature: set **`memory.enabled`** to `true` in **`llm-wiki/config.json`**.

## Pre-flight

1. Read **`llm-wiki/config.json`**. If **`memory.enabled`** is false, say so and skip writes (read-only list/show may still work for existing files).

## CLI first

Prefer shell commands; use MCP tools only when the agent has no shell (`skills/references/mcp-and-kg.md` § "CLI > MCP when local").

```bash
llm-wiki memory save --current --summary "What we did" --tags "research,ingest"
llm-wiki memory recall "topic" --tag research --limit 5
llm-wiki memory list --json
llm-wiki memory show --current
llm-wiki memory prune --keep 30
```

**`--current`** (or **`-c`**) reads **`llm-wiki/.current-session`** (updated by Claude Code hooks).

## Relationship to wiki-learn

- **`llm-wiki/.agent-memory.md`** — distilled cross-session patterns (**wiki-learn**).
- **`raw/memory/*.md`** — per-session raw records; promote recurring patterns into **`.agent-memory.md`** when appropriate.

## Recall quality

**`memory recall`** uses the vault **search backend** (`mcp.search_backend` in `config.json` — fts5, grep, chromadb, or hybrid). Results match how **`wiki_search`** / CLI search would rank the same text: keyword-heavy notes work well with **fts5**; broader or conceptual queries improve with **chromadb** / **hybrid** (optional `pip install chromadb`). See **`skills/references/mcp-and-kg.md`** § Search backends.

## `memory.max_sessions`

When **`memory.max_sessions`** is a **positive integer**, **`memory save`** and **`memory log`** run an automatic prune **after** each write: the **oldest** session files (by file modification time) are deleted until the count is ≤ the cap. Set **`0`** for unlimited files (manual **`memory prune`** only).

## Security and privacy

Session files may be **git-tracked** if the user commits **`raw/`**. Do not store API keys, tokens, or other secrets in **`raw/memory/*.md`** — keep credentials in gitignored config (e.g. **`.claude/settings.local.json`**) or env vars per **`docs/ENV.md`**.

## Done looks like

- User knows whether memory is enabled and where files live (**`raw/memory/`**).
- For writes: **`memory save`** ran with **`--current`** or an explicit session id.

## Related skills

- **wiki-learn** — cross-session distilled memory
- **wiki-query** — can **`memory recall`** when wiki lacks an answer
- **wiki-research** — recall past sessions on the same topic in pre-flight

## Smoke check

- **CLI:** `llm-wiki memory list` from vault root.
- **Prompt:** slash command **`/llm-wiki:memory`** or open **`commands/memory.md`**.
- **Config:** `memory.enabled`, `memory.dir`, `memory.max_sessions` in **`llm-wiki/config.json`**.
