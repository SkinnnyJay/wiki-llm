---
name: wiki-query
description: Answers questions using llm-wiki/wiki pages with citations. Use when the user asks about vault content or synthesized knowledge.
when_to_use: Use when a user asks for facts, summaries, or navigation from curated vault content; use wiki-research or wiki-fetch when new external evidence is needed.
allowed-tools: Read Grep Glob Bash
argument-hint: "<question about vault content>"
---

# Wiki query — Reader

Answer questions **from curated wiki pages** with **inline citations** to `wiki/` paths. Use when the user wants facts, summaries, or navigation help inside the vault (not when they need new research from the web).

## Pre-flight

1. Confirm `llm-wiki/config.json` exists (vault root). If missing, offer **wiki-setup**.
2. Read **`wiki/index.md`** to orient; open the most relevant `wiki/**/*.md` files for the question.
3. Check `config.json` for `mcp.search_backend` (`fts5` / `grep` / `chromadb` / `hybrid`) and `knowledge_graph.enabled` to decide which tools to use. **`hybrid`** needs Chroma installed; if unsure, read **`wiki_status`** / **`skills/references/mcp-and-kg.md`** for fallbacks.

> Search backend API, KG CLI, and Python examples: **`skills/references/mcp-and-kg.md`**

## Steps

### Step 1 — Scope the question

- If the question is vague, narrow it or list candidate pages from `wiki/index.md`.
- If the answer is not in the wiki, say so and offer **wiki-research** or **wiki-fetch** instead of inventing sources.
- If **`memory.enabled`** is true, optionally run **`llm-wiki memory recall "<terms>"`** for past session notes under **`raw/memory/`** before giving up.
- **Search shortcut:** When the vault is large or the question targets specific terms, use the CLI search for BM25-ranked results (see reference § "Search"). Prefer CLI locally; fall back to MCP `wiki_search` only when shell access is unavailable.

### Step 1b — Query the knowledge graph (when enabled)

If **`knowledge_graph.enabled`** is true, run `llm-wiki kg query "<entity>"` for structured relationships — see reference § "CLI quick reference".

### Step 2 — Answer with citations

- Cite paths inline, e.g. `` `wiki/topics/foo.md` `` or `` [[Topic]] `` when listing sources.
- Prefer quoting short spans; for long passages, point to the file and section.
- When the knowledge graph provides structured facts, cite both the KG triple and the source wiki page.

### Step 3 — Optional persistence

- If the answer should live in the vault, offer to save as a new **`wiki/`** page (linked from the index) or under **`outputs/`** as a draft to verify before promoting to wiki.

## Done looks like

- The user’s question is answered using **only** (or primarily) **`wiki/`** content, with **at least one citation** per non-obvious claim.
- If nothing relevant exists in the wiki, you **state the gap** and suggest **wiki-research** / **wiki-fetch** / **wiki-ingest** as next steps.
- If you created or updated a page, **`wiki/index.md`** and **`wiki/log.md`** are updated when appropriate.

## Artifacts

| Reads | Writes |
|-------|--------|
| `wiki/index.md`, `wiki/**/*.md` | Optional new `wiki/**/*.md` or `outputs/**/*.md` |

Downstream: **wiki-maintainer** if many pages change; **wiki-lint** for a health pass.

## Related skills

- **wiki-research** — add new sources and merge into wiki when the vault lacks an answer.
- **wiki-fetch** — quick single-URL ingest into `raw/` without full research orchestration.
- **wiki-ingest** / **wiki-maintainer** — merge curated content after new material lands in `raw/`.
- **wiki-lint** — audit wiki coherence after bulk edits.
- **wiki-session-memory** — recall per-chat notes in **`raw/memory/`** when enabled.

## Smoke check

- **CLI:** `llm-wiki validate` from the vault root.
- **Prompt:** Invoke this skill with a sample question; confirm answers cite paths under `wiki/`.

Optional: `skills/references/context-persona.md`; vault display name: `persona.name` in `llm-wiki/config.json` (default **Gennie**).
