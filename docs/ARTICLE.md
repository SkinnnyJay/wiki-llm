# How I built llm-wiki

Two ideas from X circled in my mind: [Karpathy’s LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) with [its discussion](https://x.com/karpathy/status/2039805659525644595), and the [MemPalace](https://github.com/milla-jovovich/mempalace) approach to external memory ([context on X](https://x.com/bensig/status/2041229266432733356)). Their intersection drove me to develop a Python CLI and a Claude Code plugin.

So I built **llm-wiki**: a **git-backed** vault turning messy sources into a maintained, agent-searchable wiki—not a chatbot, a **hub for knowledge**.

## The problem

Bookmarks decay. Chats vanish. PDFs drown in hopefully named folders.

The model can summarize whatever you paste—but a summary with nowhere to live is only a slightly louder bookmark.

## What I wanted

Karpathy gave the **habit**: sources in, maintained notes out, on a loop.

MemPalace clarified the **shape**: memory you are able to navigate—files you control—not just data inside model weights.

I wanted both features, plus the ability to use **git** (a version control system) on the vault, so each step—ingesting data, preparing raw, merging to `wiki/`, and building the viewer—creates a record you can compare or undo. This structure lets you check and use git as a record of all changes.

I wanted **measured, not assumed, retrieval**. Once the search worked, I added benchmarks.

## The loop (mental model)

This is the whole system in one pass:

- **Ingest** messy sources—URLs, PDFs, and notes—into `raw/`
- **Prepare and validate** so junk never becomes truth
- **Merge** into a living `wiki/` with wikilinks and structure
- **Build** a static viewer when you want to browse it like a site (a simple set of pages you can open in a browser—no app server required for each request)
- **Search** the same index via the **CLI** (command-line interface: a text-based way to run tools) and **MCP** (Model Context Protocol: how the host exposes tools to an agent), rather than dumping the entire vault into the model’s context window
- **Benchmark** retrieval so recall and rank quality are numbers, not vibes—you test and measure retrieval; **recall** is how often relevant items show up in the top results; **rank quality** is how well items are ordered by relevance

If the map’s clear, the rest is how.

## What makes it different

Not chat memory as a slogan.

Not a generic vector dump.

Not notes with no pipeline.

It’s **`raw/`** (messy, **untrusted**) vs **`wiki/`** (what you’ll stand behind), optional **`outputs/`** for drafts, a single **`config.json`** for operational truth—uniform workflow in an editor agent or terminal.

## How it actually ships

**`scripts/`** uses **stdlib-first Python**. A single entrypoint, **`bin/llm-wiki`**, offers ingest adapters, validation, **`build-site`** / **`build-og`**, an optional knowledge graph in JSON or SQLite, and **MCP** over stdio or SSE.

**Slash-first** in Claude Code (`commands/`, `skills/`, templates) uses slash commands, so you bypass long flag lists and let prompts handle routine tasks.

I did not want the workflow trapped in one **IDE** (integrated development environment). The repo exposes the system via slash commands, CLI, MCP, and root agent docs (**`AGENTS.md`** / **`CLAUDE.md`**, synced from **`docs/AGENTS.shared.md`**). Cursor picks up **`.cursor-plugin/`** and **`rules/llm-wiki.mdc`**; Codex reads **`AGENTS.md`**. Different hosts use the same **binary** and `raw/` → `wiki/` layout.

I ran ingestion and validation on real messy sources—URLs, PDFs, awkward HTML—and tightened prompts when the agent drifted. Testing mirrored real user workflows, not demo scripts.

## Why benchmarks matter

Vault search is easy to fake in a demo and hard to trust in production.

The **`llm-wiki benchmark`** command runs public retrieval suites (LME-style, LoCoMo, ConvoMem-style) and records metrics including **recall@K** (how often relevant items appear in the top *K*) and **NDCG@K** (ranking quality at *K*). That surfaces lexical misses, bad rankings, and regressions when you change **FTS** (full-text search), Chroma, or hybrid fusion.

It does **not** measure “did the chat remember you?” Session notes under **`raw/memory/`** and **`wiki-learn`** are separate on purpose.

**In brief:** LME stresses long haystacks and paraphrase; LoCoMo stresses **multi-hop dialogue**; ConvoMem-style suites stress **breadth**—all through one harness so configs compare fairly. Optional **peer LME** runs the same LongMemEval JSON through external memory backends (for example mem0) and records **`benchmark.peer.<id>.*`** plus rubric dimensions—see [`benchmarks/README.md`](https://github.com/SkinnnyJay/wiki-llm/blob/main/benchmarks/README.md). Paper leaderboards aren’t apples-to-apples unless splits match.

Underpinning all of this, allow me to be honest about what makes this project truly difficult:

## The hardest part is ingestion

Copying arbitrary web text into **`raw/`** creates a **trust boundary** (a line between untrusted and trusted data). The passage may end up in **model context**. **Prompt injection** (tricking models into unsafe behavior via inputs) is a real bug class—not a footnote.

So **`raw/`** is untrusted until curated. That’s not cautionary copy; it’s **part of the architecture**.

## What stuck

The project stayed honest because I ran the full loop on my own mess: capture, structure, validate, ship a viewer, wire search, repeat.

The point was never “make a smarter chatbot.”

It was to give knowledge a **real home**: inspectable, editable, searchable, benchmarked, and versioned.

**Same vault and workflow—different agents.**

**Repo:** [github.com/SkinnnyJay/wiki-llm](https://github.com/SkinnnyJay/wiki-llm)  
**Docs:** [skinnnyjay.github.io/wiki-llm](https://skinnnyjay.github.io/wiki-llm/)
