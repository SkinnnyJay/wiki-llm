---
description: Initialize or reconfigure a llm-wiki vault. Runs the interactive wiki-setup wizard — asks questions, shows a full preview, then commits config.json and scaffolds vault directories.
---

# Setup / reconfigure vault

Follow the **wiki-setup** skill for a fully guided wizard. The wizard checks **`_meta.setup_completed`**, walks integrations and persona, **MCP server / search backend**, **knowledge graph**, shows a **full `config.json` preview** before writing, then scaffolds the vault.

## Quick usage

```bash
llm-wiki setup --root .
llm-wiki configure -i
llm-wiki integrations validate
```

After setup, register the MCP server with your editor: `llm-wiki mcp install`. Seed the knowledge graph from existing wiki pages: `llm-wiki kg rebuild`.

Non-interactive: see **wiki-setup** skill.

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.
