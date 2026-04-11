<p align="center">
  <img src="assets/readme-banner.png" alt="llm-wiki" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/SkinnnyJay/wiki-llm" title="Repository on GitHub"><img src="https://img.shields.io/badge/GitHub-repo-181717?logo=github&logoColor=white" alt="GitHub repo"/></a>
  &nbsp;
  <a href="https://github.com/SkinnnyJay/wiki-llm#install-claude-code" title="Install the plugin in Claude Code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-D4A574?logo=anthropic&logoColor=white" alt="Claude Code plugin"/></a>
  &nbsp;
  <a href="https://github.com/SkinnnyJay/wiki-llm/blob/main/AGENTS.md" title="AGENTS.md for Cursor and Codex"><img src="https://img.shields.io/badge/Cursor-rules%20%2B%20plugin-000000?logo=cursor&logoColor=white" alt="Cursor rules"/></a>
</p>


# llm-wiki — quickstart

**How these docs are ordered:** **Claude Code** (slash commands + skills) first, then the **`llm-wiki`** **CLI**, then **bash / shell** snippets for scripts, CI, and copy-paste automation.

---

**Terminology**

| Term | Meaning |
|------|---------|
| **Vault** | Your knowledge folder (usually `./llm-wiki/` inside a project): `wiki/`, `raw/`, `config.json`, etc. |
| **Plugin repo** | This **wiki-llm** repository: CLI, skills, commands, and templates — not your vault. |

**Cursor / Codex:** open this repo and use [`AGENTS.md`](../AGENTS.md); prompts live in [`commands/`](../commands/) (same text as **`/llm-wiki:…`**).

---

## Five-minute path (basic)

### 1. Claude Code (recommended)

Install and reload (see **[`INSTALL.md`](./INSTALL.md)** for detail), then in chat:

```text
/reload-plugins
/llm-wiki:setup
```

Merge **`raw/`** into **`wiki/`** with skills **wiki-ingest** and **wiki-maintainer** (or **`/llm-wiki:ingest`**). The CLI does not auto-write topic pages — that curation step is intentional.

### 2. CLI (same vault, terminal)

From the **plugin repo** root with `bin/llm-wiki` on your `PATH` (or `./bin/llm-wiki`):

```bash
llm-wiki setup --root . --defaults
llm-wiki --vault ./llm-wiki ingest file ./README.md --out notes/readme-clip.md
llm-wiki --vault ./llm-wiki validate
llm-wiki --vault ./llm-wiki build-site
```

Use **`llm-wiki --help`** and **`llm-wiki <cmd> --help`** for flags. Full reference: [`CLI.md`](./CLI.md).

### 3. Bash / shell (optional)

Equivalent using explicit paths to the repo binary (good for scripts or one-off runs):

```bash
./bin/llm-wiki setup --root . --defaults
./bin/llm-wiki --vault ./llm-wiki ingest file ./README.md --out notes/readme-clip.md
./bin/llm-wiki --vault ./llm-wiki validate
./bin/llm-wiki --vault ./llm-wiki build-site
```

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
| Claude Code install, `/reload-plugins`, dev clone | [`INSTALL.md`](./INSTALL.md) |
| Slash commands — index and details | [`SLASH-COMMANDS.md`](./SLASH-COMMANDS.md) |
| Slash prompt files (`/llm-wiki:…`) | [`commands/`](../commands/) |
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
