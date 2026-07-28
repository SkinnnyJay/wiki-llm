# Setup wizard runbook

Use this reference only after **wiki-setup** has selected a full, vault-only, or memory-only route.

## Routes

| Route | Configure |
|---|---|
| Full | Vault and optional session memory |
| Vault only | Vault settings; preserve `memory.*` |
| Memory only | Existing vault's `memory.*` settings only |

For a memory-only request, require an existing configuration. For a fresh vault, direct the user to full or vault-only setup.

## Questions to collect

Ask one group at a time and retain answers until the preview:

1. Vault location and persona name.
2. Vault Git policy: enabled, automatic snapshots, or disabled.
3. Integrations: configure, defer, or disable each available adapter. Never persist API keys without explicit user direction.
4. Ingestion-security policy: log, block, or disable scanning.
5. Research-loop enablement and task file.
6. Default PDF adapter.
7. MCP search backend and knowledge-graph backend.
8. Session-memory enablement, directory, and retention limit (full or memory-only routes).
9. Static viewer settings.

For backend options, use [`../../references/mcp-and-kg.md`](../../references/mcp-and-kg.md). For quick installation paths, use [`../../../docs/QUICKSTART.md`](../../../docs/QUICKSTART.md).

## Preview and apply

1. Render the complete effective `config.json`, including every changed key and the resolved vault location.
2. Ask for explicit confirmation before scaffolding or writing anything.
3. On confirmation, run `llm-wiki setup` with the selected root and apply the approved values.
4. Mark `_meta.setup_completed: true` only after the write succeeds.
5. Suggest `llm-wiki doctor` and `llm-wiki integrations status` after setup.

Do not print API keys in the preview, logs, or final summary. If the user cancels, write nothing.
