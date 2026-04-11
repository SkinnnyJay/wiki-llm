---
name: setup
description: Root setup entry — vault (llm-wiki) and/or session memory. Full wizard body lives in skills/wiki-setup/SKILL.md.
---

# Setup — vault and/or session memory

## Claude Code — “unknown skill” / slash not found

- **Prefer the slash menu:** type **`/`**, then filter with **`setup`**, **`llm`**, or **`wiki`**. Do not hand-type Skill-tool IDs unless the UI documents them.
- **Two valid plugin ids** (same workflow): **`llm-wiki:setup`** (this file) and **`llm-wiki:wiki-setup`** (directory skill `skills/wiki-setup/SKILL.md`).
- After changing the plugin: **`/reload-plugins`**. Re-add the marketplace if needed, or use **`claude plugin marketplace update llm-wiki-local`** when your CLI exposes the **`claude plugin`** subcommands.
- **If every plugin skill is “unknown”:** Claude Code **skips `skills/`** when the plugin repo contains a **`.claude/`** directory (e.g. synced rules or **`settings.local.json`**). Remove or relocate that folder so the plugin root has no **`.claude/`** (use **`~/.claude/settings.json`** for personal env). See [anthropics/claude-code#44120](https://github.com/anthropics/claude-code/issues/44120).

Full wizard steps, routing, and Section 8c (memory) are in **`skills/wiki-setup/SKILL.md`**.

---

## In Claude (slash commands)

| Slash | Use for |
|-------|---------|
| **`/llm-wiki:setup`** | New vault, full re-wizard, **vault-only**, or **memory-only** — follows **wiki-setup** (preview before write). |
| **`/llm-wiki:configure`** | **Quick tweaks** to existing **`config.json`** — MCP **`wiki_configure`**, **`llm-wiki configure -i`**, or guided edits. See **`commands/configure.md`**. |
| **`/llm-wiki:status`** | **Health check** — integrations, config, search/KG, optional tool checks; MCP **`wiki_status`**. See **`commands/status.md`** (**wiki-status** skill). |

**`/llm-wiki:setup`** is the **root entry** for configuration. It maps to the **wiki-setup** skill, which defines two **tracks** that share one preview/commit discipline:

| Track | What it configures | When to use |
|--------|-------------------|-------------|
| **Vault (llm-wiki) setup** | `vault_root`, persona, git, integrations, MCP/search, KG, viewer, research loop, etc. | New vaults or reconfiguring the wiki pipeline |
| **Memory setup** | `memory.enabled`, `memory.dir`, `memory.max_sessions` — per-chat notes under **`raw/memory/`**, hooks, `llm-wiki memory …` | Enabling or adjusting session memory only |

## How the wizard behaves

1. **Full run (default)** — Walk **vault** sections in order; at **Session memory** (skill **Section 8c — memory-setup**) either configure `memory.*` or skip and leave defaults. One **preview** of `config.json` before write (iron rule in **wiki-setup**).
2. **Vault only** — Same sections but **skip Section 8c** (memory stays off or unchanged). User can run memory later via **`/llm-wiki:setup`** again and choose **memory-only**, or jump to Section 8c in **wiki-setup**.
3. **Memory only** — **Requires** an existing vault and **`config.json`**. Only Section **8c**; merge `memory.*` into the current file (preview shows memory keys + any touched defaults).

Tracks **2** and **3** are independent CLI/agent flows; **1** runs both when the user wants a single pass.

## Quick CLI (outside chat)

```bash
llm-wiki setup --root .
llm-wiki configure -i
llm-wiki integrations validate
# Optional: JS-heavy pages — pip install playwright && playwright install chromium  (then: llm-wiki ingest playwright …)
```

Session memory is still toggled in **`llm-wiki/config.json`** until a dedicated **`memory setup`** CLI exists; use **wiki-setup** Section 8c in chat for guided **`memory.*`** keys and hooks pointers.

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run **`/llm-wiki:setup`** or **`/llm-wiki:wiki-setup`** and confirm the agent follows **wiki-setup** routing (full vs vault-only vs memory-only).
