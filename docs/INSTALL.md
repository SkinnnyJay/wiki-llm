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
