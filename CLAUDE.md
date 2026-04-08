# AGENTS — wiki-llm

**Mirror:** same content as **[`AGENTS.md`](AGENTS.md)** (canonical for Codex); keep them in sync when updating this overview.

This repo is the **llm-wiki** plugin: a **Python CLI** (`bin/llm-wiki`), **slash-command prompts** (`commands/`), **skills** (`skills/*/SKILL.md`), and **agent personas** (`agents/`, **`prompts/PERSONA.md`**). Vault layout is **`raw/`** (sources) → **`wiki/`** (curated markdown) + optional **`outputs/`** (drafts/reports); see **`ETHOS.md`** and **`WORKFLOWS.md`**.

## How each tool uses this repository

| Tool | Mechanism | Best reference |
|------|-----------|----------------|
| **Claude Code** | **`/.claude-plugin/plugin.json`** — install via Anthropic plugin marketplace; slash commands map to **`commands/*.md`**. | [Discover plugins](https://docs.anthropic.com/en/discover-plugins), [`README.md`](README.md) |
| **Cursor** | **Project rules:** **`rules/llm-wiki.mdc`** (canonical); also available as **`.cursor/rules/llm-wiki.mdc`** (symlink so Cursor discovers them). **Cursor Marketplace plugins** use **`.cursor-plugin/plugin.json`** plus **`rules/`**, **skills**, MCP, hooks — see Cursor docs. | [Cursor plugins](https://cursor.com/docs/plugins), [Rules](https://docs.cursor.com/en/context/rules), [Publish a plugin](https://cursor.com/marketplace/publish) |
| **OpenAI Codex CLI** | Walks the tree for **`AGENTS.md`** / **`AGENTS.override.md`** (and optional fallbacks in **`~/.codex/config.toml`**). Merges from repo root down; size limit applies. | [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md/) |

This file (**`AGENTS.md`**) is optimized for **Codex** and any agent that reads a single root instruction file. **Cursor** still loads **`rules/*.mdc`** automatically when you open the repo; you do not have to duplicate vault prose into **`AGENTS.md`** unless you want Codex to see it without opening **`rules/`**.

## Claude Code (first-class)

Install the plugin from the marketplace (see [`README.md`](README.md)), then use **`/llm-wiki:…`** commands. Each command’s text lives in **`commands/<name>.md`** (same content as the slash command).

## Cursor (editor + optional Marketplace plugin)

- **Clone and open:** Rules live in **`rules/llm-wiki.mdc`**. **`AGENTS.md`** (this file) is extra context if you paste it or if your team mirrors it into rules.
- **Marketplace:** Cursor plugins bundle **rules, skills, MCP, hooks, subagents** ([announcement](https://cursor.com/blog/marketplace)). This repo ships **`.cursor-plugin/plugin.json`** next to **`/.claude-plugin/`** so maintainers can submit the same codebase to the [Cursor Marketplace](https://cursor.com/marketplace/publish) (curated review). Until listed, use clone + **`rules/`** like any project.

There is no separate “VS Code extension” for llm-wiki — automation is the **CLI** + agent instructions above.

## OpenAI Codex CLI

Codex loads **`AGENTS.md`** before tasks ([discovery order](https://developers.openai.com/codex/guides/agents-md/)). Use **`bin/llm-wiki`** from a terminal and **`commands/*.md`** as manual prompts. If instructions exceed the default byte budget, raise **`project_doc_max_bytes`** in **`~/.codex/config.toml`** or split overrides into nested **`AGENTS.override.md`** files.

## Common workflows (all tools)

1. **CLI** — `bin/llm-wiki` (works from any cwd if invoked by absolute path) or `python3 scripts/llm_wiki.py` **from the repo root** for `setup`, `ingest`, `validate`, `raw validate` / `raw record` / **`raw finish`** (validate + log + `[prepare]` commit), `build-site`, `graph`, `git`, `research-loop`, etc. (Do not use `PYTHONPATH=scripts`—relative `PYTHONPATH` can crash Python 3.14+ at startup; the script adds `scripts/` to `sys.path` automatically.)
2. **Commands as prompts** — Open **`commands/<name>.md`**; same text as **`/llm-wiki:…`**.
3. **Skills** — **wiki-pipeline** (end-to-end vault flow), **wiki-maintainer**, **wiki-ingest**, **wiki-raw-prepare**, **wiki-query**, **wiki-lint**, **wiki-status**, **wiki-setup**, **wiki-research** (ad-hoc topic), **wiki-research-loop** (batch tasks), **wiki-retro**, **wiki-learn** (`.agent-memory.md`), **wiki-upgrade** (plugin repo pull) in **`skills/*/SKILL.md`**. Pipeline artifacts: **`skills/references/pipeline-artifacts.md`**.
4. **Context** — **`WORKFLOWS.md`**, **`ETHOS.md`**, **`prompts/PERSONA.md`**.

**Static viewer “Open file”:** In **`llm-wiki/config.json`**, set **`viewer.open_file_scheme`** to **`cursor`** or **`vscode`** when you want wiki links to open the editor.

## User projects (after `llm-wiki setup`)

A scaffolded vault lives under **`llm-wiki/`** with **`llm-wiki/CLAUDE.md`** (vault rules). If your tool only reads **`AGENTS.md`** at the project root, **copy or summarize** the relevant rules from **`llm-wiki/CLAUDE.md`** so Codex-style agents see the same constraints. You can also add **`CLAUDE.md`** to Codex’s **`project_doc_fallback_filenames`** if you standardize on that filename.
