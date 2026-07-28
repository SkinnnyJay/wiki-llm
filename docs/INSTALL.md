# Install

For the complete first-run flow, follow the [five-minute quickstart](./QUICKSTART.md). It explains the plugin repo versus your vault and includes the first Claude Code and CLI commands.

## Claude Code

```text
/plugin marketplace add https://github.com/SkinnnyJay/wiki-llm
/plugin install llm-wiki@llm-wiki-local
/reload-plugins
```

The marketplace catalog is [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json).

Then continue with [`QUICKSTART.md`](./QUICKSTART.md). To update an installed plugin, run `/plugin marketplace update`.

## Development clone

Run `./setup`, then either use `claude --plugin-dir /path/to/wiki-llm` for a one-off session or install the local marketplace. Validate the plugin with:

```bash
claude plugin validate /path/to/wiki-llm
```

Cursor and Codex use [`AGENTS.md`](../AGENTS.md), [`rules/llm-wiki.mdc`](../rules/llm-wiki.mdc), and `bin/llm-wiki`; they do not use the Claude Code plugin install.

## PyPI / pip (CLI + MCP modules only)

`pip install llm-wiki` (or a built wheel) ships the **Python CLI and MCP modules** under `scripts/` — enough to run `llm-wiki` and `import mcp_server`. It does **not** install Claude/Cursor plugin assets (`skills/`, `commands/`, `hooks/`, templates). For those, clone this repo or install from the marketplace (see above).

