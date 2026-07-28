<p align="center">
  <img src="docs/assets/readme-banner.png" alt="llm-wiki" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/SkinnnyJay/wiki-llm" title="Repository on GitHub"><img src="https://img.shields.io/badge/GitHub-repo-181717?logo=github&logoColor=white" alt="GitHub repo"/></a>
  &nbsp;
  <a href="https://github.com/SkinnnyJay/wiki-llm#install-claude-code" title="Install the plugin in Claude Code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-D4A574?logo=anthropic&logoColor=white" alt="Claude Code plugin"/></a>
  &nbsp;
  <a href="https://github.com/SkinnnyJay/wiki-llm/blob/main/AGENTS.md" title="AGENTS.md for Cursor and Codex"><img src="https://img.shields.io/badge/Cursor-rules%20%2B%20plugin-000000?logo=cursor&logoColor=white" alt="Cursor rules"/></a>
</p>

# llm-wiki

**llm-wiki** is a **Claude Code plugin** (and a small Python CLI) that helps you keep a **personal knowledge vault** next to your projects. You capture sources into **`raw/`**, curate linked markdown in **`wiki/`**, and optionally generate a **static viewer**, wire **MCP search**, or turn on **session memory**—so your agent has a durable place to read and write, not a one-off chat dump.

It turns scattered source material into a **maintained wiki** your agent can keep improving over time—**slash-command first** (e.g. **`/llm-wiki:setup`**, **`/llm-wiki:ingest`**, **`/llm-wiki:build-og`**), without living in flag hell. **Quick setup (docs site):** [skinnnyjay.github.io/wiki-llm/index.html#setup](https://skinnnyjay.github.io/wiki-llm/index.html#setup).

This repository is the **plugin**: commands, skills, templates, and `bin/llm-wiki`. After setup, your **vault** usually lives at **`./llm-wiki/`** inside whatever repo you chose (terminology is at the top of **[`docs/QUICKSTART.md`](docs/QUICKSTART.md)**).

<a id="install-claude-code"></a>

## Start here

**New to llm-wiki? Follow the [five-minute path in `docs/QUICKSTART.md`](docs/QUICKSTART.md).** It distinguishes the plugin repo from your vault and gives the first Claude Code and CLI commands. For installation variants only, see [`docs/INSTALL.md`](docs/INSTALL.md).

## Inspiration

> If I have seen further it is by standing on the shoulders of Giants.

— Isaac Newton, letter to Robert Hooke (1675).

The workflow borrows from **[Andrej Karpathy’s “LLM Wiki” gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)** and **[Karpathy on X](https://x.com/karpathy/status/2039805659525644595)**—a simple pattern for turning sources into maintained notes—and from ideas in the **[MemPalace](https://github.com/milla-jovovich/mempalace)** line of work (**[Milla & Ben on X](https://t.co/tQaFQWWn4y)**; [more context](https://x.com/bensig/status/2041229266432733356)). The goal here is a **concrete plugin** for Claude Code (and friends) with ingest, validation, and agent-facing skills—not a generic “memory product.”

**Feature list** (vault, session memory, MCP recall, benchmarks, and more): **[`docs/INSPIRATION.md`](docs/INSPIRATION.md)**.

## The wiki

We treat the vault as **sources first, then curated notes**—not one undifferentiated pile of markdown.

- **`raw/`** — Ingested captures (files, URLs, feeds, APIs) land here with explicit paths; optional **raw prepare** cleans messy HTML/PDF/OCR before you merge.
- **`wiki/`** — The maintained layer: wikilinks, **`wiki/index.md`**, **`wiki/log.md`**, and topic pages. **wiki-ingest** and **wiki-maintainer** help fold `raw/` into structure without losing coherence.
- **Ship** — Validate, **wiki-lint**, optional **vault git** with lifecycle-tagged commits, then **`build-site`** for a static viewer (serve over HTTP, not `file://`).
- **See the shape** — On-demand **wikilink graphs**, optional **knowledge-graph** triples, and **MCP** search (BM25 by default; optional semantic/hybrid) so agents can navigate what you stored.
- **Go wide** — Topic research and batch loops (**`/llm-wiki:research`**, **wiki-research-loop**) plan sources → `raw/` → `wiki/` with logging.

Evidence, trust, and why **`raw/`** and **`wiki/`** differ: **[`ETHOS.md`](ETHOS.md)**.

- **Ingest risk** — Scraping or ingesting URLs copies **arbitrary text** into `raw/` and later into model context. That includes **prompt-injection** patterns and **bad-faith** pages meant to mislead automations or readers—**use at your discretion**. This plugin does not sanitize the web for you. See **[`docs/THREAT-MODEL.md`](docs/THREAT-MODEL.md)**, **[`skills/references/access-sources-disclaimer.md`](skills/references/access-sources-disclaimer.md)**, and **[`ETHOS.md` — Ingestion and security](ETHOS.md#ingestion-and-security)**.

## Memory

We split **vault knowledge**, **chat continuity**, and **retrieval evaluation**—so “memory” stays understandable and under your control.

- **Session memory** (opt-in, **`memory.enabled`**) — Per-chat notes in **`raw/memory/`**; **save**, **recall**, **list**, **prune** via **`llm-wiki memory …`** or **`/llm-wiki:memory`**. Recall ranks the same way as vault search (FTS5 / grep / optional Chroma / hybrid).
- **Learn file** — **`llm-wiki/.agent-memory.md`** (**wiki-learn**) holds durable patterns you promote from sessions or the wiki—compact, editable, next to the vault.
- **MCP** — With **`llm-wiki mcp`**, the host can search the wiki, query the KG, and use session memory tools without dumping whole chats into context.
- **Benchmarks** — **`llm-wiki benchmark`** runs optional **LME / LoCoMo / ConvoMem**-style retrieval tests over the vault index. That measures **search quality**, not “remembering the conversation.”

More detail: **[`docs/INSPIRATION.md`](docs/INSPIRATION.md)** (full feature survey).

---

## Setup

Use the [five-minute quickstart](docs/QUICKSTART.md) for the primary path. It covers plugin installation, `/llm-wiki:setup`, and the equivalent `llm-wiki setup --root . --defaults` flow without duplicating the wizard here.

---

## Usage (the loop)

1. **Capture** — Ingest files or URLs into `raw/` (e.g. `llm-wiki ingest file …`, `ingest url …`).  
2. **Curate** — In chat, use **`/llm-wiki:…`** commands and skills such as **wiki-ingest** / **wiki-maintainer** to merge material into `wiki/` with wikilinks and structure.  
3. **Ship / browse** — `llm-wiki validate`, then `llm-wiki build-site` (or **`build-og --serve`** / **`--serve-background`**; stop background with **`build-og --stop-serving`**) so the viewer is over HTTP (not `file://`).

Minimal end-to-end example:

```bash
llm-wiki setup --root .
llm-wiki ingest file ./README.md --out notes/readme-clip.md
# Build + local HTTP in one step (port from viewer.port, default 8765):
llm-wiki build-og --serve-background
echo "Viewer on disk: $(pwd)/llm-wiki/wiki/.og/"
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
| Web ingest, legal access, untrusted content / prompt injection | [`skills/references/access-sources-disclaimer.md`](skills/references/access-sources-disclaimer.md) |
| Security boundaries and hardening | [`docs/THREAT-MODEL.md`](docs/THREAT-MODEL.md) |
| Tool-specific wiring (Claude / Cursor / Codex) | [`AGENTS.md`](AGENTS.md) |
| Slash commands — index, summaries, CLI hints | [`docs/SLASH-COMMANDS.md`](docs/SLASH-COMMANDS.md) |
| Slash prompt sources (`commands/*.md`) | [`commands/`](commands/) |
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

Common subcommands: **`setup`**, **`ingest`**, **`validate`**, **`build-site`**, **`configure`** (`-i` interactive), **`raw validate` / `raw finish`**, **`memory …`** (when enabled), **`mcp`**, **`kg …`**, **`benchmark …`**, **`check`**, **`sync-agent-docs`**. Use **`llm-wiki --help`** and **`llm-wiki <cmd> --help`** for flags; **WORKFLOWS** and **QUICKSTART** cover the happy paths.

---

## Configuration (quick)

Toggles live in **`llm-wiki/config.json`**: viewer, integrations, git, research loop, ingestion security, optional hooks, and **`persona.name`** (default **Gennie**). For sound hooks, ingest policy, viewer serving, and git lifecycle, see **[Configuration (full)](#configuration-full)** below and **[`WORKFLOWS.md`](WORKFLOWS.md)**.

---

## Slash commands, skills, and agents (overview)

**Full index** (every **`/llm-wiki:…`**, summary, links to prompt files and CLI): **[`docs/SLASH-COMMANDS.md`](docs/SLASH-COMMANDS.md)**. In Claude Code, **`/llm-wiki:…`** maps to **[`commands/`](commands/)**. Skills live under **[`skills/*/SKILL.md`](skills/)** (e.g. **wiki-pipeline**, **wiki-ingest**, **wiki-maintainer**, **wiki-query**, **wiki-research**, **wiki-research-loop**, **wiki-lint**, **wiki-retro**, **wiki-session-memory**). Agents are in **[`agents/`](agents/)**. See **[`WORKFLOWS.md`](WORKFLOWS.md)** for day-to-day flows.

---

## Example: from zero to graph

```bash
# Development: load plugin (e.g. claude --plugin-dir /path/to/wiki-llm)

llm-wiki setup --root .
llm-wiki ingest file ./README.md --out notes/readme-copy.md
llm-wiki ingest hackernews --limit 5 --out research/hn-sample.md

# In chat: merge raw → wiki (wiki-ingest / wiki-maintainer), then:
llm-wiki build-og --serve-background
echo "Viewer on disk: $(pwd)/llm-wiki/wiki/.og/"

# Optional: link graph bundle
llm-wiki graph-knowledge
echo "Graph bundle: $(pwd)/.tmp/llm-wiki-graph/  →  http://127.0.0.1:8890/"
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

[`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json) lists the local marketplace entry.

---

## Privacy and telemetry

No phone-home telemetry from the plugin. Optional APIs (Firecrawl, Perplexity, etc.) use **your** keys. Vault and session memory stay **local** unless you sync them yourself.

---

## License

MIT — see [LICENSE](LICENSE).
