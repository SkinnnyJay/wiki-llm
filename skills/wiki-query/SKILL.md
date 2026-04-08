---
name: wiki-query
description: Answers questions using llm-wiki/wiki pages with citations. Use when the user asks about vault content or synthesized knowledge.
---

# Wiki query

**Layered recall protocol (L0 → L3):**

1. **L0+L1** — Read `## Memory Stack` in `llm-wiki/CLAUDE.md` (or run `llm-wiki wake-up`).
   This gives you the vault name, topic list with wiki coverage, and recent log entries in ~170 tokens.
2. **L2** — If the query matches a known topic, open `wiki/**/*.md` pages whose filename or
   content matches that topic. Check `raw/.tags.json` to find all raw files tagged with that topic.
3. **L3** — If wiki/ pages don't fully answer the question, open the tagged `raw/` files directly.
   Prefer `raw/` files whose `llm_wiki_tags` frontmatter includes the query topic.
4. **Answer** with inline citations (file paths). If the answer is durable knowledge, offer to
   promote it to `wiki/` (linked from `wiki/index.md`). If it's a one-off report, file under `outputs/`.

**Graceful degradation:** If `## Memory Stack` is missing or tags don't exist yet,
fall back to reading `wiki/index.md` directly (previous behaviour).

Optional: `skills/references/context-persona.md` for tool-calling tone;
vault name from `persona.name` in `config.json` (default **Gennie**).
