<p align="center">
  <img src="assets/readme-banner.png" alt="llm-wiki" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/SkinnnyJay/wiki-llm"><img src="https://img.shields.io/badge/GitHub-repo-181717?logo=github&logoColor=white" alt="GitHub repository"/></a>
  <a href="https://github.com/SkinnnyJay/wiki-llm#install-claude-code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-D4A574?logo=anthropic&logoColor=white" alt="Claude Code: install instructions"/></a>
  <a href="https://github.com/SkinnnyJay/wiki-llm/blob/main/AGENTS.md"><img src="https://img.shields.io/badge/Cursor-rules%20%2B%20plugin-000000?logo=cursor&logoColor=white" alt="Cursor: AGENTS.md"/></a>
</p>


# Inspiration

> If I have seen further it is by standing on the shoulders of Giants.

— Isaac Newton, letter to Robert Hooke (1675).

The workflow borrows from **[Andrej Karpathy’s “LLM Wiki” gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)**—a simple pattern for turning sources into maintained notes—and from ideas in the **[MemPalace](https://github.com/milla-jovovich/mempalace)** line of work ([context](https://x.com/bensig/status/2041229266432733356)). The goal of **llm-wiki** is a **concrete plugin** for Claude Code (and friends) with ingest, validation, and agent-facing skills—not a generic “memory product.”

**How features are described below:** **Claude Code** (slash commands + skills) first, then **CLI** (`llm-wiki`), then **bash / shell** when it is mainly for scripts or servers.

## What’s in the box

### Vault and curation

- **Claude Code** — **`/llm-wiki:ingest`**, **wiki-ingest**, **wiki-maintainer**, **wiki-lint**, **wiki-pipeline**; merge **`raw/`** → **`wiki/`** with wikilinks and structure.
- **CLI** — **`llm-wiki ingest`**, **`validate`**, **`build-site`**, **`graph`**, **`graph-knowledge`**; with **`git.enabled`**, **`llm-wiki git snapshot`**, **`git lifecycle`**, etc.
- **Bash / shell** — Serve **`wiki/.og/`** with **`python3 -m http.server`** (not `file://`); optional pipelines around the same commands.

### Ingest and raw prep

- **Claude Code** — **`/llm-wiki:ingest`**, **wiki-raw-prepare**, skills for specific sources.
- **CLI** — **`llm-wiki ingest`**, **`raw validate`**, **`raw finish`**.
- **Details** — **`outputs/`** for drafts; **`--out`** stays under **`raw/`**.

### Static viewer and graphs

- **Claude Code** — **`/llm-wiki:build-og`** (viewer); **`/llm-wiki:graph`**, **`/llm-wiki:graph-knowledge`** (same ideas as CLI).
- **CLI** — **`build-site`** → **`wiki/.og/`**; **`graph`** / **`graph-knowledge`**; **Knowledge-graph** triples (JSON or SQLite) via **`llm-wiki kg`**.
- **Bash / shell** — **`cd llm-wiki/wiki/.og && python3 -m http.server …`**; same for **`.tmp/llm-wiki-graph/`** when exploring graphs.

### Memory and recall

- **Claude Code** — **`/llm-wiki:memory`** when **`memory.enabled`**; **wiki-session-memory**; **`/llm-wiki:mcp`** exposes search + memory tools to the host.
- **CLI** — **`llm-wiki memory save|recall|list|show|prune`**; same search backends as the vault (**fts5**, **grep**, optional **Chroma** / **hybrid**). **`--current`** uses **`.current-session`** from hooks.
- **Cross-session** — **`llm-wiki/.agent-memory.md`** (**wiki-learn**), promoted from session notes when useful.

### Research and quality

- **Claude Code** — **`/llm-wiki:research`**, **`/llm-wiki:research-loop`**, **wiki-research**, **wiki-research-loop**, **wiki-retro**.
- **CLI** — **`llm-wiki research-loop`**, **`benchmark …`** (retrieval evaluation — not “chat memory” in the product sense).

### How to run it

1. **Claude Code** — Slash index: [`SLASH-COMMANDS.md`](./SLASH-COMMANDS.md); prompt files: [`commands/`](../commands/); skills: [`skills/`](../skills/).
2. **CLI** — [`CLI.md`](./CLI.md), [`WORKFLOWS.md`](../WORKFLOWS.md).
3. **Bash / shell** — [`INSTALL.md`](./INSTALL.md) § Bash / shell, [`QUICKSTART.md`](./QUICKSTART.md) § Bash / shell.

**Next:** [`QUICKSTART.md`](./QUICKSTART.md), [`../ETHOS.md`](../ETHOS.md).
