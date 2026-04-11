---
description: Change vault settings after setup — MCP wiki_configure, CLI configure -i, or wiki-setup sections.
---

# Configure — vault settings (without full re-setup)

**`/llm-wiki:configure`** is the **quick path** to change **`llm-wiki/config.json`** after the vault exists. For a **full wizard** or **memory-only** (`memory.*`), use **`/llm-wiki:setup`** (wiki-setup) instead. To **verify** the vault after changes, use **`/llm-wiki:status`** (**`commands/status.md`** / **wiki-status**).

## When to use what

| Situation | What to do |
|-----------|------------|
| One or a few keys (e.g. `mcp.search_backend`, `knowledge_graph.enabled`) | This command: **MCP `wiki_configure`** when connected, else **`llm-wiki configure -i`** or a small **preview → confirm → write** edit |
| Several toggles in one pass (viewer, git, MCP, KG, search backend) | **`llm-wiki configure -i`** in a terminal (interactive wizard) |
| Session memory only (`memory.enabled`, `memory.dir`, …) | **`/llm-wiki:setup`** → **memory-only** track, or **wiki-setup** Section **8c** |
| Full vault reconfigure | **`/llm-wiki:setup`** → **full** or **vault-only** |

## MCP `wiki_configure` (when MCP is connected)

- **Inputs:** `key` — dot-separated path (e.g. `mcp.search_backend`); `value` — string (parsed as JSON when valid).
- **Examples:** `mcp.search_backend` → `"hybrid"`; `mcp.enabled` → `"true"` (JSON boolean); `viewer.enabled` → `"false"`.
- **Allowlist:** If **`mcp.configure_allowlist`** is a **non-empty** list, only matching keys are allowed. **Empty** allowlist means any key is allowed (see vault **`config.json`** / **`scripts/lib/config_loader.py`** defaults).

## CLI (terminal)

```bash
# Interactive — persona, OG URL, feature toggles, MCP, search backend, KG
llm-wiki configure -i

# Non-interactive (see flags)
llm-wiki configure --help
```

Vault resolution: **`LLM_WIKI_VAULT`**, **`--vault`**, or default **`./llm-wiki`** (same as other `llm-wiki` commands).

## Agent workflow (Claude)

1. **Resolve vault** — confirm path (`LLM_WIKI_VAULT`, `./llm-wiki`, or user-provided).
2. **Ask what to change** — map user intent to dot path(s); read current **`config.json`** if helpful.
3. **Prefer MCP** — if **`wiki_configure`** is available and the key is allowlisted (or allowlist is empty), call it after the user confirms the new value.
4. **No MCP** — run **`llm-wiki configure -i`** (user terminal) **or** show a **preview diff** of `config.json` and write only after explicit confirmation (same **iron rule** as wiki-setup for destructive overwrites).
5. **Follow-ups** — after search/MCP/backend changes, mention **`llm-wiki validate`** and reindex / **`kg rebuild`** when relevant (see **`skills/references/mcp-and-kg.md`**).

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** From a project with a vault, run **`llm-wiki configure -i`**, save, and confirm **`config.json`** updated.
- **Prompt:** With MCP enabled, change one safe key via **`wiki_configure`** and verify the file on disk.
