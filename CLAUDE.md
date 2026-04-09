# AGENTS — wiki-llm

**Mirror:** same content as **[`AGENTS.md`](AGENTS.md)** (canonical for Codex); keep them in sync when changing the tool list or plugin overview. **Plugin workflows** are maintained in **[`docs/AGENTS.shared.md`](docs/AGENTS.shared.md)** and synced with **`bin/llm-wiki sync-agent-docs`** (or **`python3 scripts/sync_agent_docs.py`**).

<!-- BEGIN AGENTS_SHARED -->
## Repo summary

This repo is the **llm-wiki** plugin: a **Python CLI** (`bin/llm-wiki`), **slash-command prompts** (`commands/`), **skills** (`skills/*/SKILL.md`), and **agent personas** (`agents/`, **`prompts/PERSONA.md`**). Vault layout is **`raw/`** (sources) → **`wiki/`** (curated markdown) + optional **`outputs/`** (drafts/reports); see **`ETHOS.md`** and **`WORKFLOWS.md`**.

## Common workflows (all tools)

1. **CLI** — `bin/llm-wiki` (works from any cwd if invoked by absolute path) or `python3 scripts/llm_wiki.py` **from the repo root** for `setup`, `ingest`, `validate`, `raw validate` / `raw record` / **`raw finish`** (validate + log + `[prepare]` commit), `build-site`, `graph`, `git`, `research-loop`, etc. (Do not use `PYTHONPATH=scripts`—relative `PYTHONPATH` can crash Python 3.14+ at startup; the script adds `scripts/` to `sys.path` automatically.)
2. **Commands as prompts** — Open **`commands/<name>.md`**; same text as **`/llm-wiki:…`**.
3. **Skills** — **wiki-pipeline** (end-to-end vault flow), **wiki-maintainer**, **wiki-ingest**, **wiki-raw-prepare**, **wiki-query**, **wiki-lint**, **wiki-status**, **wiki-setup**, **wiki-research** (ad-hoc topic), **wiki-research-loop** (batch tasks), **wiki-retro**, **wiki-learn** (`.agent-memory.md`), **wiki-upgrade** (plugin repo pull) in **`skills/*/SKILL.md`**. Pipeline artifacts: **`skills/references/pipeline-artifacts.md`**.
4. **Context** — **`WORKFLOWS.md`**, **`ETHOS.md`**, **`prompts/PERSONA.md`**.
5. **Agent doc sync (this plugin repo only)** — After editing **`docs/AGENTS.shared.md`**, run **`bin/llm-wiki sync-agent-docs`** to refresh **`AGENTS.md`**, **`CLAUDE.md`**, **`rules/llm-wiki.mdc`**, and **`.claude/rules/llm-wiki.md`**. Before merge, **`bin/llm-wiki sync-agent-docs --check`** (or **`bin/llm-wiki check --plugin-repo`**) must pass. Equivalent: **`python3 scripts/sync_agent_docs.py`** from the repo root.

**Static viewer “Open file”:** In **`llm-wiki/config.json`**, set **`viewer.open_file_scheme`** to **`cursor`** or **`vscode`** when you want wiki links to open the editor.

**Python:** Match existing style in **`scripts/`**; run tests or **`python3 -m compileall`** if you touch CLI code. Personal/demo scripts belong in **`scripts/.tmp/`** (gitignored), not tracked **`scripts/`**.

When editing the **vault template** under **`templates/llm-wiki/`**, keep **`llm-wiki/CLAUDE.md`** and **`config.json`** schema consistent with **`README.md`** and **`WORKFLOWS.md`**.
<!-- END AGENTS_SHARED -->

## How each tool uses this repository

| Tool | Mechanism | Best reference |
|------|-----------|----------------|
| **Claude Code** | **`/.claude-plugin/plugin.json`** — install via Anthropic plugin marketplace; slash commands map to **`commands/*.md`**. | [Discover plugins](https://docs.anthropic.com/en/discover-plugins), [`README.md`](README.md) |
| **Cursor** | **Project rules:** **`rules/llm-wiki.mdc`** (canonical); also available as **`.cursor/rules/llm-wiki.mdc`** (symlink so Cursor discovers them). **Cursor Marketplace plugins** use **`.cursor-plugin/plugin.json`** plus **`rules/`**, **skills**, MCP, hooks — see Cursor docs. | [Cursor plugins](https://cursor.com/docs/plugins), [Rules](https://cursor.com/docs/context/rules), [Publish a plugin](https://cursor.com/marketplace/publish) |
| **OpenAI Codex CLI** | Walks the tree for **`AGENTS.md`** / **`AGENTS.override.md`**. Project knobs: **`.codex/config.toml`** (this repo) and **`~/.codex/config.toml`**. Merges from repo root down; size limit applies. | [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md/) |

This file (**`CLAUDE.md`**) mirrors **`AGENTS.md`** for tools that read `CLAUDE.md` instead of **`AGENTS.md`**. **Cursor** still loads **`rules/*.mdc`** automatically when you open the repo; the rule body matches the shared block above.

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
