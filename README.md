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

**Compile source documents into a trusted, agent-ready knowledge base.**

llm-wiki is the **knowledge compiler** for coding agents: raw papers, URLs, PDFs, and notes go in; a small, cross-linked, citation-backed **`wiki/`** comes out—then every agent (Claude Code, Cursor, Codex, MCP) can search that *compiled* truth instead of re-RAG’ing a junk drawer on every prompt.

**What this replaces (30 seconds):** chat dumps that evaporate, undifferentiated “RAG folders,” and hope-the-model-remembered.  
**What this is not:** NotebookLM (chat over files), Obsidian (a note app), Mem0/MemPalace (session memory), or another paste-into-Claude template.

| Loop step | Meaning |
|-----------|---------|
| **Ingest** | Evidence lands in immutable **`raw/`** |
| **Compile** | Agents/skills merge into curated **`wiki/`** with provenance |
| **Query** | **`llm-wiki search`**, MCP, or skills answer from the compiled wiki first |

Primary path: **Claude Code marketplace / git clone** + slash commands. Optional: Cursor/`AGENTS.md`, CLI-only wheel (no templates). Terminology and the five-minute path: **[`docs/QUICKSTART.md`](docs/QUICKSTART.md)**. Install variants: **[`docs/INSTALL.md`](docs/INSTALL.md)**.

<a id="install-claude-code"></a>

## Start here

1. Install (Claude Code) or clone this repo — see **[`docs/INSTALL.md`](docs/INSTALL.md)**.
2. Run the **[five-minute path](docs/QUICKSTART.md)** through **ingest → compile (wiki-ingest) → `search`**.
3. For evidence layers and trust: **[`ETHOS.md`](ETHOS.md)**.

Docs site shortcut: [skinnnyjay.github.io/wiki-llm/index.html#setup](https://skinnnyjay.github.io/wiki-llm/index.html#setup).

## Compile one source (recipe)

```bash
llm-wiki setup --root . --defaults
llm-wiki --vault ./llm-wiki ingest file ./README.md --out notes/readme-clip.md
# Compile step (agent): /llm-wiki:ingest  →  updates wiki/*.md from raw/
llm-wiki --vault ./llm-wiki lint          # deterministic wiki health (when available)
llm-wiki --vault ./llm-wiki search "llm-wiki"
# Optional MCP: llm-wiki mcp
```

## Inspiration (pattern → product)

> If I have seen further it is by standing on the shoulders of Giants.

— Isaac Newton, letter to Robert Hooke (1675).

The workflow borrows from **[Andrej Karpathy’s “LLM Wiki” gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)**—compile once, query the wiki—and related local-first memory ideas. Karpathy’s gist is the **pattern**; llm-wiki productizes **compilation quality**: provenance, lint gates, KG contradictions, MCP delivery. Full feature survey: **[`docs/INSPIRATION.md`](docs/INSPIRATION.md)**.

## The compiler layers

- **`raw/`** — Immutable evidence (ingest adapters, copies). Untrusted until compiled.
- **`wiki/`** — Compiled knowledge: wikilinks, **`index.md`**, **`log.md`**, topic pages with sources.
- **Gates** — **`validate`**, **`lint`**, **wiki-lint** (agent), optional knowledge tests — knowledge CI.
- **Delivery** — **`search`**, MCP tools (prefer compiled pages), optional static viewer / graphs.

Evidence vs claims: **[`ETHOS.md`](ETHOS.md)**. Ingest copies arbitrary web text—prompt injection is real: **[`docs/THREAT-MODEL.md`](docs/THREAT-MODEL.md)**.

## Setup

Use the [five-minute quickstart](docs/QUICKSTART.md). Covers `/llm-wiki:setup` and `llm-wiki setup --root . --defaults`.

---

## Usage (the loop)

1. **Ingest** — `llm-wiki ingest file|url …` → **`raw/`**.  
2. **Compile** — **`/llm-wiki:ingest`** / **wiki-ingest** (and maintainer) → **`wiki/`**.  
3. **Query** — `llm-wiki search "…"`, or MCP; then optionally `validate` / `lint` / `build-site`.

```bash
llm-wiki setup --root .
llm-wiki ingest file ./README.md --out notes/readme-clip.md
# In chat: /llm-wiki:ingest
llm-wiki search "readme"
```

**Full green path:** **[`WORKFLOWS.md`](WORKFLOWS.md)**.

---

## Optional (not the product)

Session memory, retrieval benchmarks, research loops, graphs, and the Agent desk (`apps/web`) are **optional modules**—useful, but they are not the knowledge compiler. See **[`docs/INSPIRATION.md`](docs/INSPIRATION.md)** when you want them.

---

## Documentation map

| You want… | Read |
|-----------|------|
| Compile one source end-to-end | This README recipe + [`docs/QUICKSTART.md`](docs/QUICKSTART.md) |
| Five-minute setup and tiers | [`docs/QUICKSTART.md`](docs/QUICKSTART.md) |
| Install variants | [`docs/INSTALL.md`](docs/INSTALL.md) |
| Inspiration + optional features | [`docs/INSPIRATION.md`](docs/INSPIRATION.md) |
| Vault vs plugin, data flow | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Day-to-day flows and ops | [`WORKFLOWS.md`](WORKFLOWS.md) |
| Web ingest / prompt injection | [`skills/references/access-sources-disclaimer.md`](skills/references/access-sources-disclaimer.md) |
| Security boundaries | [`docs/THREAT-MODEL.md`](docs/THREAT-MODEL.md) |
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

Common subcommands: **`setup`**, **`doctor`**, **`search`**, **`ingest`**, **`validate`**, **`lint`**, **`diff`**, **`compile`**, **`build-site`**, **`configure`** (`-i`), **`raw …`**, **`mcp`**, **`kg …`**, optional **`memory`** / **`benchmark`**, **`check`**. Happy path: **QUICKSTART** (ingest → compile → search).

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
