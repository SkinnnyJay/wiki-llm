# Install and first run

**Terminology:** **Vault** = your `llm-wiki/` folder; **plugin repo** = this repository (CLI, commands, skills). See [`QUICKSTART.md`](./QUICKSTART.md).

<a id="install-claude-code"></a>

## Claude Code (recommended): slash commands first

1. Add the marketplace and install **llm-wiki** (catalog name in [`marketplace.json`](../marketplace.json): `llm-wiki-local`):

   ```text
   /plugin marketplace add https://github.com/SkinnnyJay/wiki-llm
   /plugin install llm-wiki@llm-wiki-local
   ```

2. Run **`/reload-plugins`** so **`/llm-wiki:…`** slash commands and **`skills/`** load.

3. **Scaffold the vault in chat:** **`/llm-wiki:setup`** (same text as [`commands/setup.md`](../commands/setup.md)). That creates **`llm-wiki/`** with `raw/`, `wiki/`, `config.json`, and vault rules.

4. **Next commands:** **`/llm-wiki:status`** (health), **`/llm-wiki:configure`** (quick config). Use **`/llm-wiki:ingest`** and skills **wiki-ingest**, **wiki-maintainer**, **wiki-pipeline** for the ongoing loop. Every prompt lives under [`commands/`](../commands/) (`/llm-wiki:<name>` → `commands/<name>.md`).

After upstream plugin changes: **`/plugin marketplace update`**. Official docs: [Discover and install plugins](https://docs.anthropic.com/en/discover-plugins), [plugin marketplaces](https://docs.anthropic.com/en/docs/claude-code/plugin-marketplaces).

**Note:** GitHub cannot install the plugin for you. VS Code–style `vscode:extension/…` links apply to **published extensions**, not Claude **plugin** marketplaces.

---

## Cursor / OpenAI Codex

No Claude **plugin** install — use **[`AGENTS.md`](../AGENTS.md)**, project rules **[`rules/llm-wiki.mdc`](../rules/llm-wiki.mdc)**, and **`commands/*.md`** as manual prompts (same text as **`/llm-wiki:…`**). Run **`bin/llm-wiki`** from a terminal when you need the CLI.

<a id="install-development--clone"></a>

## Development (clone of this repo)

```bash
./setup
```

Load the plugin in Claude Code:

- **One-off session:** `claude --plugin-dir /path/to/wiki-llm` — [CLI reference](https://code.claude.com/docs/en/cli-reference).
- **Persistent:** `/plugin marketplace add /path/to/wiki-llm`, **`/plugin install llm-wiki@llm-wiki-local`**, **`/reload-plugins`**.

Local installs copy the tree into `~/.claude/plugins/cache/` (not `.gitignore`-aware). For a slimmer tree: **`./scripts/plugin_dev_slim.sh`** (dry-run, then `--apply`), or use `claude --plugin-dir` for daily dev.

```bash
claude plugin validate /path/to/wiki-llm
# or in chat: /plugin validate
```

**Troubleshooting** (plugin missing, cache, ENOSPC): [`WORKFLOWS.md`](../WORKFLOWS.md) “Troubleshooting (green path)”.

---

## Optional: scripted CLI (CI or power users)

The same scaffold and loop are available via **`llm-wiki`** — see [`QUICKSTART.md`](./QUICKSTART.md) and [`WORKFLOWS.md`](../WORKFLOWS.md) “Green path”. [`CLI.md`](./CLI.md) lists subcommands and the `PYTHONPATH` note.

### Example: ingest → viewer → graph

```bash
# With plugin loaded (e.g. claude --plugin-dir /path/to/wiki-llm)

llm-wiki setup --root .
llm-wiki ingest file ./README.md --out notes/readme-copy.md
llm-wiki ingest hackernews --limit 5 --out research/hn-sample.md

# In chat: merge raw → wiki (wiki-ingest / wiki-maintainer), then:
llm-wiki build-site
cd llm-wiki/wiki/.og && python3 -m http.server 8765

# Optional: link graph bundle
llm-wiki graph-knowledge
cd .tmp/llm-wiki-graph && python3 -m http.server 8890
```
