# Install

For the complete first-run flow, follow the [five-minute quickstart](./QUICKSTART.md). It explains the plugin repo versus your vault and includes the first Claude Code and CLI commands.

## What ships where

| Install path | You get | Vault `setup` / skills / hooks |
|--------------|---------|--------------------------------|
| **Claude Code marketplace** or **git clone** | Full plugin (`skills/`, `commands/`, `templates/`, `bin/llm-wiki`) | Yes |
| **Cursor / Codex** (open clone + `AGENTS.md` / rules) | Same checkout assets | Yes |
| **`pip install .` / wheel** (optional) | Python **CLI + MCP modules** only | **No** — clone or marketplace for scaffolding |

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

```bash
./bin/llm-wiki setup --root . --defaults
./bin/llm-wiki --vault ./llm-wiki doctor
```

## Optional: pip / wheel (CLI + MCP modules only)

From a clone you can build/install the wheel for CLI/MCP import smoke:

```bash
pip install .
llm-wiki --version
```

That install does **not** include `templates/`, `skills/`, or `commands/`. `llm-wiki setup` will refuse with a clear error pointing here. Prefer `./bin/llm-wiki` from a full checkout (or marketplace) for day-to-day use.

A public PyPI package is **not** required for the plugin; do not assume `pip install llm-wiki` from PyPI until a release publishes it.
