# Inspiration

> If I have seen further it is by standing on the shoulders of Giants.

— Isaac Newton, letter to Robert Hooke (1675).

The workflow borrows from **[Andrej Karpathy’s “LLM Wiki” gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)**—a simple pattern for turning sources into maintained notes—and from ideas in the **[MemPalace](https://github.com/milla-jovovich/mempalace)** line of work ([context](https://x.com/bensig/status/2041229266432733356)). The goal of **llm-wiki** is a **concrete plugin** for Claude Code (and friends) with ingest, validation, and agent-facing skills—not a generic “memory product.”

## What’s in the box

**Vault and curation**

- **Sources → notes** — Capture into **`raw/`**, curate linked markdown in **`wiki/`**, optional **`outputs/`** for drafts and reports; validation, wikilinks, and **wiki-lint**-style health checks.
- **Ingest** — Files, URLs, feeds, and more via **`llm-wiki ingest`** and **`/llm-wiki:ingest`**; **wiki-raw-prepare** / **`raw finish`** for messy captures.
- **Static viewer** — **`build-site`** emits a browsable wiki under **`wiki/.og/`** (serve over HTTP, not `file://`).
- **Graphs** — Wikilink graphs and optional **knowledge-graph** triples (JSON or SQLite) for relationships and timelines.
- **Vault git** — Optional lifecycle-tagged commits (`git.enabled`, phase prefixes, **`git lifecycle`**).

**Memory and recall**

- **Session memory** (opt-in, **`memory.enabled`**) — Per-chat notes under **`raw/memory/`**; **`llm-wiki memory save`**, **`recall`**, **`list`**, **`show`**, **`prune`**. **Recall** searches past sessions so the agent can tie this chat’s work to earlier decisions—using the same search backend as the vault (**fts5**, **grep**, optional **Chroma** / **hybrid**). Hooks can maintain **`.current-session`** for **`--current`**.
- **Cross-session learn file** — **`llm-wiki/.agent-memory.md`** (**wiki-learn**) for durable patterns you promote from session notes or wiki work—not a second vault, but a small, editable layer next to it.
- **MCP** — When the editor hosts **`llm-wiki mcp`**, tools can **search the wiki**, query the **knowledge graph**, run **ingest/validate**, and use **session memory** so project context and **vault content** stay addressable without pasting huge logs.

**Research and quality**

- **Ad-hoc and batch research** — **`/llm-wiki:research`**, **`research-loop`** (tasks in config), **`wiki-research`**, **wiki-retro** for periodic summaries.
- **Retrieval benchmarks** — Optional **LME / LoCoMo / ConvoMem**-style runs (**`llm-wiki benchmark`**) with metrics in the vault—evaluation of search quality, not chat “memory” in the product sense.

**How to run it** — Slash commands (**`/llm-wiki:…`**, files in [`commands/`](../commands/)), skills under [`skills/`](../skills/), CLI [`CLI.md`](./CLI.md), full flows [`WORKFLOWS.md`](../WORKFLOWS.md).

**Next:** [`QUICKSTART.md`](./QUICKSTART.md), [`../ETHOS.md`](../ETHOS.md).
