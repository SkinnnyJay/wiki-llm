# AGENTS — wiki-llm

**Canonical copy:** this file is the source of truth for Codex-style discovery. **[`CLAUDE.md`](CLAUDE.md)** mirrors it for tools that read `CLAUDE.md`. **Plugin workflows** are edited in **[`docs/AGENTS.shared.md`](docs/AGENTS.shared.md)** and synced here (and into **`rules/llm-wiki.mdc`**) with **`bin/llm-wiki sync-agent-docs`** (or **`python3 scripts/sync_agent_docs.py`**).

<!-- BEGIN AGENTS_SHARED -->
## Repo summary

This repo is the **llm-wiki** plugin: a **Python CLI** (`bin/llm-wiki`), **slash-command prompts** (`commands/`), **skills** (`skills/*/SKILL.md`), and **agent personas** (`agents/`, **`prompts/PERSONA.md`**). Vault layout is **`raw/`** (sources) → **`wiki/`** (curated markdown) + optional **`outputs/`** (drafts/reports); see **`ETHOS.md`** and **`WORKFLOWS.md`**. **First-time setup:** **`docs/QUICKSTART.md`** (vault vs plugin repo, five-minute path, basic/intermediate/advanced tiers).

## Common workflows (all tools)

1. **CLI** — `bin/llm-wiki` (works from any cwd if invoked by absolute path) or `python3 scripts/llm_wiki.py` **from the repo root** for `setup`, `ingest`, `validate`, `raw validate` / `raw record` / **`raw finish`** (validate + log + `[prepare]` commit; `raw/memory/` skipped), `build-site`, `graph`, `git`, `research-loop`, **`memory {save|log|list|show|recall|prune}`** (session memory under **`raw/memory/` when `memory.enabled`**, opt-in), etc. **`/llm-wiki:setup`** (see **`commands/setup.md`**) is the slash entry for **wiki-setup**: combined **vault + optional session memory (Section 8c)**, or **vault-only** / **memory-only** tracks. (Do not use `PYTHONPATH=scripts`—relative `PYTHONPATH` can crash Python 3.14+ at startup; the script adds `scripts/` to `sys.path` automatically.)
2. **Commands as prompts** — Open **`commands/<name>.md`**; same text as **`/llm-wiki:…`**.
3. **Skills** — **wiki-pipeline** (end-to-end vault flow), **wiki-maintainer**, **wiki-ingest**, **wiki-raw-prepare**, **wiki-query**, **wiki-lint**, **wiki-status**, **wiki-setup**, **wiki-research** (ad-hoc topic), **wiki-research-loop** (batch tasks), **wiki-retro**, **wiki-learn** (`.agent-memory.md`), **wiki-session-memory** (`raw/memory/` per-chat notes), **wiki-upgrade** (plugin repo pull) in **`skills/*/SKILL.md`**. Pipeline artifacts: **`skills/references/pipeline-artifacts.md`**.
4. **Context** — **`WORKFLOWS.md`**, **`ETHOS.md`**, **`prompts/PERSONA.md`**.
5. **Agent doc sync (this plugin repo only)** — After editing **`docs/AGENTS.shared.md`**, run **`bin/llm-wiki sync-agent-docs`** to refresh **`AGENTS.md`**, **`CLAUDE.md`**, **`rules/llm-wiki.mdc`**, and **`.claude/rules/llm-wiki.md`**. Before merge, **`bin/llm-wiki sync-agent-docs --check`** (or **`bin/llm-wiki check --plugin-repo`**) must pass. Equivalent: **`python3 scripts/sync_agent_docs.py`** from the repo root.

**MCP server:** `bin/llm-wiki mcp` starts a **stdio** JSON-RPC server (default) exposing vault tools (search, knowledge graph, ingest, validate, session memory, etc.). **`bin/llm-wiki mcp --transport sse --port 8891`** starts an **HTTP** listener on `mcp.host`/`mcp.port` (default `127.0.0.1:8891`): POST `/` or `/mcp` with a JSON-RPC body, `application/json` response (stdlib `scripts/mcp_sse.py`). Plugin marketplace installs auto-register stdio via `mcpServers` in **`.claude-plugin/plugin.json`** and **`.cursor-plugin/plugin.json`**. Manual install: **`bin/llm-wiki mcp install`**. Config in **`llm-wiki/config.json`**: **`mcp.enabled`**, **`mcp.transport`** (`stdio` | `sse`), **`mcp.port`** / **`mcp.host`**, **`mcp.search_backend`** (`fts5` default — BM25 via stdlib sqlite3 | `grep` | `chromadb` — semantic embeddings; requires `pip install chromadb`, falls back to **grep** if missing | `hybrid` — FTS5 + Chroma reciprocal-rank fusion; requires Chroma, falls back to **fts5** if missing), **`mcp.hybrid_rrf_k`** (RRF `k` for hybrid only, default **60**), **`knowledge_graph.backend`** (`json` | `sqlite`), **`knowledge_graph.auto_update_on_ingest`** (runs **`kg rebuild`** after ingest post-processing), **`memory.enabled`** / **`memory.dir`** / **`memory.max_sessions`** (opt-in session memory). Prefer **CLI** when running locally; use MCP when the host only exposes tools.

**Knowledge graph CLI:** `bin/llm-wiki kg {add|query|invalidate|timeline|stats|rebuild}` — entity-relationship triples in **`llm-wiki/.kg.json`** (default) or **`.kg.sqlite3`** when `knowledge_graph.backend=sqlite`. Shared reference: **`skills/references/mcp-and-kg.md`**.

**Session memory CLI:** `bin/llm-wiki memory {save|log|list|show|recall|prune}` — per-chat files under **`llm-wiki/raw/memory/`** when **`memory.enabled`**; hooks write **`llm-wiki/.current-session`** for **`--current`**.

**Benchmark CLI:** `bin/llm-wiki benchmark {run|suites|report|history|compare|analyze}` — retrieval benchmarks (LME / LoCoMo / ConvoMem) and metrics under **`benchmark.*`**. Guide: **`benchmarks/README.md`**.

**Static viewer “Open file”:** In **`llm-wiki/config.json`**, set **`viewer.open_file_scheme`** to **`cursor`** or **`vscode`** when you want wiki links to open the editor.

**Python:** Match existing style in **`scripts/`**; run tests or **`python3 -m compileall`** if you touch CLI code. Personal/demo scripts belong in **`scripts/.tmp/`** (gitignored), not tracked **`scripts/`**. Optional pip deps (**`requirements-optional.txt`**, e.g. Chroma): use a **venv**; **PEP 668** / externally managed interpreters often block global `pip install` — see **README**.

When editing the **vault template** under **`templates/llm-wiki/`**, keep **`llm-wiki/CLAUDE.md`** and **`config.json`** schema consistent with **`README.md`** and **`WORKFLOWS.md`**.
<!-- END AGENTS_SHARED -->

## How each tool uses this repository

| Tool | Mechanism | Best reference |
|------|-----------|----------------|
| **Claude Code** | **`/.claude-plugin/plugin.json`** — install via Anthropic plugin marketplace; slash commands map to **`commands/*.md`**. | [Discover plugins](https://docs.anthropic.com/en/discover-plugins), [`README.md`](README.md) |
| **Cursor** | **Project rules:** **`rules/llm-wiki.mdc`** (canonical); also available as **`.cursor/rules/llm-wiki.mdc`** (symlink so Cursor discovers them). **Cursor Marketplace plugins** use **`.cursor-plugin/plugin.json`** plus **`rules/`**, **skills**, MCP, hooks — see Cursor docs. | [Cursor plugins](https://cursor.com/docs/plugins), [Rules](https://cursor.com/docs/context/rules), [Publish a plugin](https://cursor.com/marketplace/publish) |
| **OpenAI Codex CLI** | Walks the tree for **`AGENTS.md`** / **`AGENTS.override.md`**. Project knobs: **`.codex/config.toml`** (this repo) and **`~/.codex/config.toml`**. Merges from repo root down; size limit applies. | [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md/) |

This file (**`AGENTS.md`**) is optimized for **Codex** and any agent that reads a single root instruction file. **Cursor** still loads **`rules/*.mdc`** automatically when you open the repo; the rule body matches the shared block above.

## Claude Code (first-class)

Install the plugin from the marketplace (see [`README.md`](README.md)), then use **`/llm-wiki:…`** commands. Each command’s text lives in **`commands/<name>.md`** (same content as the slash command).

## Cursor (editor + optional Marketplace plugin)

- **Clone and open:** Rules live in **`rules/llm-wiki.mdc`**. **`AGENTS.md`** (this file) is extra context if you paste it or if your team mirrors it into rules.
- **Marketplace:** Cursor plugins bundle **rules, skills, MCP, hooks, subagents** ([announcement](https://cursor.com/blog/marketplace)). This repo ships **`.cursor-plugin/plugin.json`** next to **`/.claude-plugin/`** so maintainers can submit the same codebase to the [Cursor Marketplace](https://cursor.com/marketplace/publish) (curated review). Until listed, use clone + **`rules/`** like any project.

There is no separate “VS Code extension” for llm-wiki — automation is the **CLI** + agent instructions above.

## OpenAI Codex CLI

Codex loads **`AGENTS.md`** before tasks ([discovery order](https://developers.openai.com/codex/guides/agents-md/)). Use **`bin/llm-wiki`** from a terminal and **`commands/*.md`** as manual prompts. If instructions exceed the byte budget, raise **`project_doc_max_bytes`** in **`~/.codex/config.toml`** or **`.codex/config.toml`**, or split overrides across nested **`AGENTS.override.md`** files.

## User projects (after `llm-wiki setup`)

A scaffolded vault lives under **`llm-wiki/`** with **`llm-wiki/CLAUDE.md`** (vault rules). If your tool only reads **`AGENTS.md`** at the project root, **copy or summarize** the relevant rules from **`llm-wiki/CLAUDE.md`** so Codex-style agents see the same constraints. You can also add **`CLAUDE.md`** to Codex’s **`project_doc_fallback_filenames`** if you standardize on that filename.
