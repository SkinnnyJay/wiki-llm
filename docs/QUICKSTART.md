# llm-wiki — quickstart

**Terminology**

| Term | Meaning |
|------|---------|
| **Vault** | Your knowledge folder (usually `./llm-wiki/` inside a project): `wiki/`, `raw/`, `config.json`, etc. |
| **Plugin repo** | This **wiki-llm** repository: CLI, skills, commands, and templates — not your vault. |

Install the plugin (Claude Code) or open this repo in Cursor/Codex and use [`AGENTS.md`](../AGENTS.md) for tool-specific wiring.

---

## Five-minute path (basic)

From the **plugin repo** root (or with `bin/llm-wiki` on your `PATH`):

```bash
./bin/llm-wiki setup --root . --defaults
```

This creates **`./llm-wiki/`** with `wiki/`, `raw/`, `config.json`, and `CLAUDE.md`.

Then:

```bash
# Optional: copy a file into raw/ or use ingest
./bin/llm-wiki --vault ./llm-wiki ingest file ./README.md --out notes/readme-clip.md

./bin/llm-wiki --vault ./llm-wiki validate
./bin/llm-wiki --vault ./llm-wiki build-site
```

**In chat:** merge `raw/` into curated `wiki/` using the **wiki-ingest** / **wiki-maintainer** skills (or `/llm-wiki:ingest`). The CLI does not auto-write topic pages — that step is intentional curation.

**Next:** full green path, troubleshooting, and optional features → [`WORKFLOWS.md`](../WORKFLOWS.md).

---

## Capability tiers

| Tier | You want… | Start here |
|------|-------------|------------|
| **Basic** | A working vault: capture → curate → browse | This page → [`WORKFLOWS.md`](../WORKFLOWS.md) “Green path” |
| **Intermediate** | Git history, static viewer, health checks | [`WORKFLOWS.md`](../WORKFLOWS.md), **wiki-lint** skill, `git.enabled` / `viewer` in `config.json` |
| **Advanced** | MCP in the editor, hybrid search, knowledge graph, benchmarks | [`skills/references/mcp-and-kg.md`](../skills/references/mcp-and-kg.md), [`benchmarks/README.md`](../benchmarks/README.md) |
| **Maintainer** | Plugin development, tests, agent-doc sync | [`CONTRIBUTING.md`](../CONTRIBUTING.md), [`docs/PUBLISHING.md`](./PUBLISHING.md) |

---

## Feature → doc map

| Feature | Doc |
|---------|-----|
| Slash commands (`/llm-wiki:…`) | [`commands/`](../commands/) |
| Skills (wiki-ingest, wiki-query, …) | [`skills/*/SKILL.md`](../skills/) |
| Session memory (`memory.enabled`, `raw/memory/`) | [`skills/wiki-session-memory/SKILL.md`](../skills/wiki-session-memory/SKILL.md) |
| MCP + search backends | [`skills/references/mcp-and-kg.md`](../skills/references/mcp-and-kg.md) |
| Evidence layers, trust | [`ETHOS.md`](../ETHOS.md) |
| Architecture (vault vs plugin) | [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md) |
| Env vars (`.env`, integrations, pytest opt-in) | [`docs/ENV.md`](./ENV.md), [`../.env.example`](../.env.example) |
| GitHub Pages UI (landing + Memory hub) | [`docs/README.md`](./README.md), [`docs/css/style.css`](./css/style.css) |

---

## Example vault

A minimal sample you can copy or compare against is in **[`examples/minimal-vault/`](../examples/minimal-vault/)** in this repo.
