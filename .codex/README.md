# Codex harness (wiki-llm)

This directory is the **project-scoped Codex** layer checked into the repo.

- **`config.toml`** — merged with your user `~/.codex/config.toml` when you run Codex from a trusted copy of this project. Relative paths in values resolve from this folder.
- **Instruction text** still comes from the repository root **`AGENTS.md`** (and optional nested **`AGENTS.override.md`** files), per [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md/). Shared plugin workflows are maintained in **[`docs/AGENTS.shared.md`](../docs/AGENTS.shared.md)** and synced into **`AGENTS.md`**, **`CLAUDE.md`**, and **`rules/llm-wiki.mdc`** with **`bin/llm-wiki sync-agent-docs`** from the repo root (or **`python3 scripts/sync_agent_docs.py`**). Before merge or release, run **`bin/llm-wiki sync-agent-docs --check`** or **`bin/llm-wiki check --plugin-repo`** (see **[`CONTRIBUTING.md`](../CONTRIBUTING.md)**).

**Optional:** set `CODEX_HOME` to this directory when you want an isolated Codex profile for automation (see [the same guide](https://developers.openai.com/codex/guides/agents-md/) — *Verify your setup* / `CODEX_HOME`).
