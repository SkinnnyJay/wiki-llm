---
description: Vault health — setup flag, integrations, tools, MCP search/KG; follow wiki-status skill.
---

# Status — vault health check

**`/llm-wiki:status`** maps to the **wiki-status** skill — read **`skills/wiki-status/SKILL.md`** and run its steps (setup flag, **`llm-wiki integrations status`**, optional tool/package checks, MCP/search/KG summary). Use it at **session start**, after **setup/configure**, or when the user asks whether the vault is ready.

## When to use what

| Situation | What to do |
|-----------|------------|
| Quick structured snapshot (MCP connected) | **`wiki_status`** — vault path, raw/wiki counts, persona, search backend (configured vs active, fallback), KG backend, git flag, optional **`storage_warnings`** |
| Full dashboard (integrations, CLI tools, keys masked, FTS/index notes) | **wiki-status** skill end-to-end |
| Adapter readiness only | **`llm-wiki integrations status`** |

**Related MCP:** **`wiki_validate`** returns missing **`config.json`** / **`wiki/index.md`** / **`CLAUDE.md`** when you need a minimal structural check.

### MCP “running” vs config

Status does **not** report a live OS process (e.g. “`mcp_server.py` PID 1234”). It reports:

- **`mcp.enabled`** and search/KG settings from **`config.json`** (wiki-status Step 8).
- Whether **`llm-wiki`** is **registered** in editor MCP JSON (optional block in the skill) — not whether a subprocess is up this second.
- **`wiki_status`**: if the tool returns data, the **current** client session has a working MCP connection. It does not probe other machines or a background **SSE** server.

For **HTTP/SSE** (`llm-wiki mcp --transport sse`), use **`llm-wiki mcp start`** / host–port checks if you need “listening on port” (see **`scripts/cli/mcp_commands.py`**). **Stdio** MCP is spawned by the editor per session — there is usually nothing to poll.

## CLI (terminal)

```bash
llm-wiki integrations status
```

Vault resolution matches other commands: **`LLM_WIKI_VAULT`**, **`--vault`**, or **`./llm-wiki`**.

## Agent workflow (Claude)

1. **Resolve vault** — same as setup/configure.
2. **Prefer MCP** — if **`wiki_status`** is available, call it first for a fast summary; follow with **`llm-wiki integrations status`** or skill steps if the user wants detail.
3. **If setup incomplete** — offer **`/llm-wiki:setup`** (wiki-setup).

## Related slash commands

| Slash | Use for |
|-------|---------|
| **`/llm-wiki:setup`** | New vault or full wizard — **`commands/setup.md`** / **`skills/wiki-setup/SKILL.md`** |
| **`/llm-wiki:configure`** | Change **`config.json`** — **`commands/configure.md`** |

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** `llm-wiki integrations status` from a project with **`llm-wiki/config.json`**.
- **Prompt:** Run **`/llm-wiki:status`** or invoke **wiki-status** by name and confirm the health report matches expectations.
