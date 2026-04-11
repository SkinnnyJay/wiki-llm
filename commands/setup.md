---
description: Root setup entry — vault (llm-wiki) and/or session memory. Follows wiki-setup with optional combined wizard; tracks can run alone or together.
---

# Setup — vault and/or session memory

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
```

Session memory is still toggled in **`llm-wiki/config.json`** until a dedicated **`memory setup`** CLI exists; use **wiki-setup** Section 8c in chat for guided **`memory.*`** keys and hooks pointers.

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run **`/llm-wiki:setup`** and confirm the agent follows **wiki-setup** routing (full vs vault-only vs memory-only).
