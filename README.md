<p align="center">
  <img src="docs/assets/readme-banner.png" alt="llm-wiki" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/SkinnnyJay/wiki-llm"><img src="https://img.shields.io/badge/GitHub-repo-181717?logo=github&logoColor=white" alt="GitHub repository"/></a>
  <a href="https://github.com/SkinnnyJay/wiki-llm#install-claude-code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-D4A574?logo=anthropic&logoColor=white" alt="Claude Code: install instructions"/></a>
  <a href="https://github.com/SkinnnyJay/wiki-llm/blob/main/AGENTS.md"><img src="https://img.shields.io/badge/Cursor-rules%20%2B%20plugin-000000?logo=cursor&logoColor=white" alt="Cursor: AGENTS.md"/></a>
</p>

# llm-wiki

**llm-wiki** is a **Claude Code plugin** (and a small Python CLI) that helps you keep a **personal knowledge vault** next to your projects. You capture sources into **`raw/`**, curate linked markdown in **`wiki/`**, and optionally generate a **static viewer**, wire **MCP search**, or turn on **session memory**—so your agent has a durable place to read and write, not a one-off chat dump.

This repository is the **plugin**: commands, skills, templates, and `bin/llm-wiki`. After setup, your **vault** usually lives at **`./llm-wiki/`** inside whatever repo you chose (terminology is at the top of **[`docs/QUICKSTART.md`](docs/QUICKSTART.md)**).

**Branding / images:** The main site logo includes AI-related provenance metadata (C2PA). See **[`docs/ASSETS.md`](docs/ASSETS.md)** if you redistribute or replace assets.

---

## Inspiration

> If I have seen further it is by standing on the shoulders of Giants.

— Isaac Newton, letter to Robert Hooke (1675).

The workflow borrows from **[Andrej Karpathy’s “LLM Wiki” gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)**—a simple pattern for turning sources into maintained notes—and from ideas in the **[MemPalace](https://github.com/milla-jovovich/mempalace)** line of work ([context](https://x.com/bensig/status/2041229266432733356)). The goal here is a **concrete plugin** for Claude Code (and friends) with ingest, validation, and agent-facing skills—not a generic “memory product.”

**Feature list** (vault, session memory, MCP recall, benchmarks, and more): **[`docs/INSPIRATION.md`](docs/INSPIRATION.md)**. Alternate install paths and scripted examples: **[`docs/INSTALL.md`](docs/INSTALL.md)**.

---

## Setup (short path)

**1. Install the plugin in Claude Code** (no clone required):

```text
/plugin marketplace add https://github.com/SkinnnyJay/wiki-llm
/plugin install llm-wiki@llm-wiki-local
```

More options (local marketplace, dev workflow, validation): [Install (Claude Code)](#install-claude-code) and [Install (development — clone)](#install-development--clone) below. Cursor and Codex users: **[`AGENTS.md`](AGENTS.md)** and project rules in **[`rules/llm-wiki.mdc`](rules/llm-wiki.mdc)**.

**2. Reload and set up in chat** — Run **`/reload-plugins`**, then **`/llm-wiki:setup`** (vault wizard; same text as [`commands/setup.md`](commands/setup.md)). Try **`/llm-wiki:status`** and **`/llm-wiki:configure`**. Day-to-day: **`/llm-wiki:ingest`** and skills **wiki-ingest**, **wiki-maintainer**, **wiki-pipeline** ([`commands/`](commands/) lists every slash prompt).

**3. Or scaffold from a shell** (plugin on `PATH`, or `./bin/llm-wiki` from this repo):

```bash
llm-wiki setup --root .
# or: ./bin/llm-wiki setup --root . --defaults
```

That creates **`llm-wiki/`** with `raw/`, `wiki/`, `config.json`, and vault rules. **Deeper walkthroughs** (basic → advanced tiers, flags, examples): **[`docs/QUICKSTART.md`](docs/QUICKSTART.md)**.

---

## Usage (the loop)

1. **Capture** — Ingest files or URLs into `raw/` (e.g. `llm-wiki ingest file …`, `ingest url …`).  
2. **Curate** — In chat, use **`/llm-wiki:…`** commands and skills such as **wiki-ingest** / **wiki-maintainer** to merge material into `wiki/` with wikilinks and structure.  
3. **Ship / browse** — `llm-wiki validate`, then `llm-wiki build-site` and serve the viewer over HTTP (not `file://`).

Minimal end-to-end example:

```bash
llm-wiki setup --root .
llm-wiki ingest file ./README.md --out notes/readme-clip.md
llm-wiki build-site
cd llm-wiki/wiki/.og && python3 -m http.server 8765
# Open http://127.0.0.1:8765/
```

**Full green path, troubleshooting, git phases, MCP, benchmarks:** **[`WORKFLOWS.md`](WORKFLOWS.md)**. **Why `raw/` vs `wiki/`, evidence, and trust:** **[`ETHOS.md`](ETHOS.md)**.

---

## Documentation map

| You want… | Read |
|-----------|------|
| Five-minute setup and capability tiers | [`docs/QUICKSTART.md`](docs/QUICKSTART.md) |
| Install variants (slash-first, dev clone, scripts) | [`docs/INSTALL.md`](docs/INSTALL.md) |
| Inspiration + feature list (memory, MCP, vault) | [`docs/INSPIRATION.md`](docs/INSPIRATION.md) |
| Vault vs plugin, data flow | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Day-to-day flows and ops | [`WORKFLOWS.md`](WORKFLOWS.md) |
| Tool-specific wiring (Claude / Cursor / Codex) | [`AGENTS.md`](AGENTS.md) |
| Slash-command prompts (`/llm-wiki:…`) | [`commands/`](commands/) |
| Agent skills (`wiki-ingest`, `wiki-query`, …) | [`skills/`](skills/) |
| Environment variables and integrations | [`docs/ENV.md`](docs/ENV.md), [`.env.example`](.env.example) |
| MCP server, search backends, knowledge graph | [`skills/references/mcp-and-kg.md`](skills/references/mcp-and-kg.md) |
| Retrieval benchmarks (LME / LoCoMo / ConvoMem) | [`benchmarks/README.md`](benchmarks/README.md) |
| GitHub Pages (marketing site + Memory hub) | [`docs/README.md`](docs/README.md), [`docs/PUBLISHING.md`](docs/PUBLISHING.md) |
| Contributing and tests | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Shared agent text (synced into `AGENTS.md` / rules) | [`docs/AGENTS.shared.md`](docs/AGENTS.shared.md) |
| `config.json` reference (duplicate of README section) | [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) |
| CLI entrypoint and `PYTHONPATH` note | [`docs/CLI.md`](docs/CLI.md) |

**Persona and agents:** [`prompts/PERSONA.md`](prompts/PERSONA.md), [`agents/`](agents/).

---

## CLI at a glance

Run **`bin/llm-wiki`** from the plugin repo (any cwd if you use the absolute path to the script) or **`python3 scripts/llm_wiki.py`** **from the repository root**. Do **not** rely on `PYTHONPATH=scripts` with a relative path (Python 3.14+ can break); the script adds `scripts/` to `sys.path` itself.

Common subcommands: **`setup`**, **`ingest`**, **`validate`**, **`build-site`**, **`configure`** (`-i` interactive), **`raw validate` / `raw finish`**, **`memory …`** (when enabled), **`mcp`**, **`benchmark …`**, **`check`**, **`sync-agent-docs`**. Use **`llm-wiki --help`** and **`llm-wiki <cmd> --help`** for flags; **WORKFLOWS** and **QUICKSTART** cover the happy paths.

---

## Configuration (quick)

Toggles live in **`llm-wiki/config.json`**: viewer, integrations, git, research loop, ingestion security, optional hooks, and **`persona.name`** (default **Gennie**). For sound hooks, ingest policy, viewer serving, and git lifecycle, see **[Configuration (full)](#configuration-full)** below and **[`WORKFLOWS.md`](WORKFLOWS.md)**.

---

<a id="install-claude-code"></a>

## Install (Claude Code — no clone)

Add this repo as a **plugin marketplace**, then install **llm-wiki** (catalog name in [`marketplace.json`](marketplace.json): `llm-wiki-local`):

```text
/plugin marketplace add https://github.com/SkinnnyJay/wiki-llm
/plugin install llm-wiki@llm-wiki-local
```

After upstream changes: `/plugin marketplace update`. Official docs: [Discover and install plugins](https://docs.anthropic.com/en/discover-plugins), [plugin marketplaces](https://docs.anthropic.com/en/docs/claude-code/plugin-marketplaces).

**Note:** GitHub cannot install the plugin for you—use the steps above or clone for development. VS Code–style `vscode:extension/…` links apply to **published extensions**, not Claude **plugin** marketplaces.

<a id="install-development--clone"></a>

## Install (development — clone)

```bash
./setup
```

Load the plugin in Claude Code:

- **One-off session:** `claude --plugin-dir /path/to/wiki-llm` — see [CLI reference](https://code.claude.com/docs/en/cli-reference).
- **Persistent:** add the repo as a marketplace and **`/plugin install llm-wiki@llm-wiki-local`**, then **`/reload-plugins`**.

Local installs copy the tree into `~/.claude/plugins/cache/` (not `.gitignore`-aware). For a slimmer tree: **`./scripts/plugin_dev_slim.sh`** (dry-run, then `--apply`), or use `claude --plugin-dir` for daily dev.

```bash
claude plugin validate /path/to/wiki-llm
# or in chat: /plugin validate
```

---

## Slash commands, skills, and agents (overview)

In Claude Code, **`/llm-wiki:…`** maps to files under **[`commands/`](commands/)**. Skills live under **[`skills/*/SKILL.md`](skills/)** (e.g. **wiki-ingest**, **wiki-maintainer**, **wiki-query**, **wiki-research**, **wiki-session-memory**). Agents are in **[`agents/`](agents/)**. For the full tables that used to live here, browse those folders or see **WORKFLOWS**—the README stays an onboarding layer, not a second manual.

---

## Example: from zero to graph

```bash
# Development: load plugin (e.g. claude --plugin-dir /path/to/wiki-llm)

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

---

## Testing (plugin repo)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
llm-wiki smoke-test
```

Prefer **`llm-wiki smoke-test`** over ad-hoc `PYTHONPATH`; if you need raw pytest, use an **absolute** `PYTHONPATH` to `scripts/` (see [`CONTRIBUTING.md`](CONTRIBUTING.md)). Options: `--network`, `--claude`, `--only-contracts`; **`llm-wiki test-report`** for a Markdown matrix.

---

<a id="configuration-full"></a>

## Configuration (full)

- **`config.json`** — `viewer` (including `open_file_scheme`, `og_base_url`), `integrations`, `git`, `research_loop`, `ingestion_security`, **`hooks.sound`**, **`persona.name`**.
- **Sound hook** — Optional `hooks.sound.enabled` + `hooks.sound.command` (argv JSON); restrict executables unless `allow_arbitrary_command` is set deliberately (see **WORKFLOWS**).
- **Ingest URLs** — `ingest url` / Firecrawl allow http(s) to public hosts only; integration hosts are allowlisted.
- **Viewer** — Serve `wiki/.og/` over HTTP; **DOMPurify** on rendered bodies; **Open file** via `viewer.open_file_scheme`.
- **Ingest paths** — `--out` must stay under `raw/`.
- **Wikilinks** — `[[Page]]` / `[[page.md|label]]`; general Markdown: [Markdown Guide](https://www.markdownguide.org/basic-syntax/).
- **Vault git** — With `git.enabled`, **`llm-wiki git lifecycle`** audits commits by phase; see [`commands/git-lifecycle.md`](commands/git-lifecycle.md).

---

## Marketplace

[`marketplace.json`](marketplace.json) lists the local marketplace entry.

---

## Privacy and telemetry

No phone-home telemetry from the plugin. Optional APIs (Firecrawl, Perplexity, etc.) use **your** keys. Vault and session memory stay **local** unless you sync them yourself.

---

## License

MIT — see [LICENSE](LICENSE).
