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


# llm-wiki architecture (overview)

## Two products in one repo

| | **Vault (compiled knowledge)** | **Plugin (compiler + delivery)** |
|---|-----------|-----------------|
| **What** | Your knowledge folder (`llm-wiki/`): immutable `raw/`, curated `wiki/`, `config.json` | This repository: CLI, compile/lint gates, skills, MCP, templates |
| **Where** | Your project (or `--vault` / `LLM_WIKI_VAULT`) | Cloned / marketplace plugin path |

Optional modules (session memory, benchmarks, `apps/web`) share the same plugin but are **not** the core compiler product.

## What ships where

| Surface | Plugin clone / marketplace | pip wheel |
|---------|------------------------------|-----------|
| CLI + MCP modules | Yes | Yes |
| `templates/`, skills, commands | Yes | No (`setup` refuses) |
| Agent desk `apps/web` | Yes (optional) | No |

## Data flow (compiler)

```mermaid
flowchart TB
  subgraph vault [Vault]
    raw[raw/ evidence]
    wiki[wiki/ compiled]
    mem[raw/memory/ optional]
  end
  CLI[bin/llm-wiki ingest]
  COMP[compile / wiki-ingest]
  GATES[validate lint schema]
  SEARCH[search + MCP]
  raw --> CLI
  CLI --> COMP
  COMP --> wiki
  wiki --> GATES
  GATES --> SEARCH
  mem --> SEARCH
```

- **Ingest** writes evidence to **`raw/`**; **wiki-ingest** (in chat/skills) curates **`wiki/`**.
- **`raw validate`** skips **`raw/memory/`**; session files are still **searchable** (e.g. `scope=memory`).
- **Benchmarks** (`llm-wiki benchmark …`) exercise retrieval against the vault index; metrics go to **`storage.metrics_db`** (see [`benchmarks/README.md`](../benchmarks/README.md); optional tracked run artifacts under [`docs/memory/benchmarks/runs/`](./memory/benchmarks/runs/README.md)).

## Agent instructions

- **`docs/AGENTS.shared.md`** is the single source for **`AGENTS.md`**, **`CLAUDE.md`**, and Cursor rules — run **`bin/llm-wiki sync-agent-docs`** after edits.

## Further reading

- [`docs/QUICKSTART.md`](./QUICKSTART.md) — tiers and first commands.
- [`skills/references/mcp-and-kg.md`](../skills/references/mcp-and-kg.md) — MCP, search, KG, session memory tools.
- [`docs/THREAT-MODEL.md`](./THREAT-MODEL.md) — trust boundaries and hardening.
- [`ETHOS.md`](../ETHOS.md) — evidence layers.
