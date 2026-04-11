<p align="center">
  <img src="assets/readme-banner.png" alt="llm-wiki" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/SkinnnyJay/wiki-llm"><img src="https://img.shields.io/badge/GitHub-repo-181717?logo=github&logoColor=white" alt="GitHub repository"/></a>
  <a href="https://github.com/SkinnnyJay/wiki-llm#install-claude-code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-D4A574?logo=anthropic&logoColor=white" alt="Claude Code: install instructions"/></a>
  <a href="https://github.com/SkinnnyJay/wiki-llm/blob/main/AGENTS.md"><img src="https://img.shields.io/badge/Cursor-rules%20%2B%20plugin-000000?logo=cursor&logoColor=white" alt="Cursor: AGENTS.md"/></a>
</p>


# Install and first run

**Terminology:** **Vault** = your `llm-wiki/` folder; **plugin repo** = this repository (CLI, commands, skills). See [`QUICKSTART.md`](./QUICKSTART.md).

**Order in this doc:** **Claude Code** → **`llm-wiki` CLI** → **bash / shell** (longer examples).

<a id="install-claude-code"></a>

## 1. Claude Code (recommended)

### Install and reload

1. Add the marketplace and install **llm-wiki** (catalog name in [`marketplace.json`](../marketplace.json): `llm-wiki-local`):

   ```text
   /plugin marketplace add https://github.com/SkinnnyJay/wiki-llm
   /plugin install llm-wiki@llm-wiki-local
   ```

2. Run **`/reload-plugins`** so **`/llm-wiki:…`** slash commands and **`skills/`** load.

3. **Scaffold the vault in chat:** **`/llm-wiki:setup`** (same text as [`commands/setup.md`](../commands/setup.md)). That creates **`llm-wiki/`** with `raw/`, `wiki/`, `config.json`, and vault rules.

4. **Next:** **`/llm-wiki:status`** (health), **`/llm-wiki:configure`** (quick config). Use **`/llm-wiki:ingest`** and skills **wiki-ingest**, **wiki-maintainer**, **wiki-pipeline** for the ongoing loop. Every prompt lives under [`commands/`](../commands/) (`/llm-wiki:<name>` → `commands/<name>.md`). **Full index** (all slash names + summaries + CLI hints): [`SLASH-COMMANDS.md`](./SLASH-COMMANDS.md).

After upstream plugin changes: **`/plugin marketplace update`**. Official docs: [Discover and install plugins](https://docs.anthropic.com/en/discover-plugins), [plugin marketplaces](https://docs.anthropic.com/en/docs/claude-code/plugin-marketplaces).

**Note:** GitHub cannot install the plugin for you. VS Code–style `vscode:extension/…` links apply to **published extensions**, not Claude **plugin** marketplaces.

---

## 2. Cursor / OpenAI Codex

No Claude **plugin** install — use **[`AGENTS.md`](../AGENTS.md)**, project rules **[`rules/llm-wiki.mdc`](../rules/llm-wiki.mdc)**, and **`commands/*.md`** as manual prompts (same text as **`/llm-wiki:…`**). Use **`bin/llm-wiki`** from a terminal when you need the CLI (see below).

---

## 3. CLI (`llm-wiki`)

For **terminals, CI, and automation** — same behavior as driving the vault from chat, without slash commands.

- Entrypoint: **`bin/llm-wiki`** or **`python3 scripts/llm_wiki.py`** from the plugin repo root (see [`CLI.md`](./CLI.md) for `PYTHONPATH` and subcommands).
- Typical first run: **`llm-wiki setup --root .`**, then **`llm-wiki ingest …`**, **`validate`**, **`build-site`**.
- Full green path: [`WORKFLOWS.md`](../WORKFLOWS.md) “Green path”.

---

## 4. Bash / shell (scripts and copy-paste)

Multi-step shell flows, **`./setup`**, **`cd … && python3 -m http.server`**, and pipelines belong here — not required for day-to-day Claude Code use.

<a id="install-development--clone"></a>

### Development (clone of this repo)

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
