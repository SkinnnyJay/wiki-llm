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

**Goal:** Compile one source into an agent-ready wiki page, then **query** it.  
**Labeling:** Ingest → Compile → Query (directories stay **`raw/`** / **`wiki/`**).

---

**Terminology**

| Term | Meaning |
|------|---------|
| **Vault** | Your knowledge folder (usually `./llm-wiki/`): `wiki/`, `raw/`, `config.json`. |
| **Plugin repo** | This **wiki-llm** repository: CLI, skills, commands, templates. |
| **Compile** | Merge **`raw/`** evidence into curated **`wiki/`** (skills / pipeline), then run quality gates. |

**Primary install:** Claude Code marketplace (see **[`INSTALL.md`](./INSTALL.md)**).  
**Also:** open this clone in Cursor/Codex (`AGENTS.md`); optional wheel = CLI/MCP modules only (no scaffold).

---

## Five-minute path (basic)

### 1. Claude Code (recommended)

```text
/reload-plugins
/llm-wiki:setup
```

Then ingest a source into **`raw/`**, compile with **`/llm-wiki:ingest`** (writes **`wiki/`**), and ask via **`/llm-wiki:query`** or the CLI `search` below.

### 2. CLI (same vault)

From the **plugin repo** root:

```bash
llm-wiki setup --root . --defaults
llm-wiki --vault ./llm-wiki ingest file ./README.md --out notes/readme-clip.md
# Compile (agent): /llm-wiki:ingest  — CLI fills raw/ only; skills write wiki topic pages
llm-wiki --vault ./llm-wiki validate
llm-wiki --vault ./llm-wiki search "llm-wiki"
# Optional: llm-wiki --vault ./llm-wiki lint
# Optional: llm-wiki mcp
```

Use **`llm-wiki --help`**. Full reference: [`CLI.md`](./CLI.md).

### 3. Bash / shell (scripts)

```bash
./bin/llm-wiki setup --root . --defaults
./bin/llm-wiki --vault ./llm-wiki ingest file ./README.md --out notes/readme-clip.md
./bin/llm-wiki --vault ./llm-wiki validate
./bin/llm-wiki --vault ./llm-wiki search "llm-wiki"
```

**Next:** green path and gates → [`WORKFLOWS.md`](../WORKFLOWS.md). Ethos → [`ETHOS.md`](../ETHOS.md).

---

## Capability tiers

| Tier | You want… | Start here |
|------|-------------|------------|
| **Basic** | Ingest → compile → **search** | This page |
| **Intermediate** | Lint/schema gates, git, static viewer | [`WORKFLOWS.md`](../WORKFLOWS.md), **wiki-lint**, `viewer` in config |
| **Advanced** | MCP, hybrid search, KG contradictions | [`skills/references/mcp-and-kg.md`](../skills/references/mcp-and-kg.md) |
| **Optional** | Session memory, benchmarks, research loops, `apps/web` | [`INSPIRATION.md`](./INSPIRATION.md) (not the core pitch) |
| **Maintainer** | Plugin tests, agent-doc sync | [`CONTRIBUTING.md`](../CONTRIBUTING.md) |

---

## Feature → doc map

| Feature | Doc |
|---------|-----|
| Compile one source end-to-end | This page + README recipe |
| Claude Code install | [`INSTALL.md`](./INSTALL.md) |
| Slash commands | [`SLASH-COMMANDS.md`](./SLASH-COMMANDS.md) |
| Skills | [`skills/*/SKILL.md`](../skills/) |
| Evidence layers | [`ETHOS.md`](../ETHOS.md) |
| Architecture | [`ARCHITECTURE.md`](./ARCHITECTURE.md) |
| MCP + search | [`skills/references/mcp-and-kg.md`](../skills/references/mcp-and-kg.md) |
| Optional session memory | [`skills/wiki-session-memory/SKILL.md`](../skills/wiki-session-memory/SKILL.md) |

---

## Example vault

Minimal sample: **[`examples/minimal-vault/`](../examples/minimal-vault/)**.
