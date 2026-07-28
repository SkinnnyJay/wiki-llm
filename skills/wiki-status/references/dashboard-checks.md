# Status dashboard checks

Use this reference when the compact `llm-wiki doctor` result needs investigation or the user asks for a full environment report.

## Check groups

1. **Vault state** — resolved root, `config.json`, setup completion, and expected `raw/` and `wiki/` structure.
2. **Integrations** — run `llm-wiki integrations status`; report readiness without exposing credentials.
3. **Runtime support** — inspect only the adapters relevant to enabled integrations (for example Playwright or a selected PDF adapter).
4. **Configuration** — summarize enabled features: ingestion security, research loop, viewer, MCP backend, knowledge-graph backend, and session memory.
5. **Indexes and graph** — report missing, empty, or stale FTS5/Chroma/KG data and give the corresponding CLI remediation.
6. **Optional editor registration** — when relevant, check whether the llm-wiki MCP server is registered; suggest `llm-wiki mcp install` rather than modifying editor configuration unprompted.

## Report format

Group results as ready, attention, missing, or optional. State the exact safe next command for each actionable problem. Do not enumerate every optional package or API key unless the user asked for an exhaustive diagnostic.

## Remediation

- Missing vault or incomplete setup: offer **wiki-setup**.
- Missing adapter requirement: point to `llm-wiki integrations status` or the relevant setup route.
- Empty knowledge graph: suggest `llm-wiki kg rebuild`.
- Missing FTS5/Chroma index: explain that it is created on search or reindex it through the supported CLI/MCP path.
