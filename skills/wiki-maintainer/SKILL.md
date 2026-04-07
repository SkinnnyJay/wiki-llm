---
name: wiki-maintainer
description: Maintains the LLM Wiki vault — index, log, cross-links, contradictions. Use when editing llm-wiki/wiki/, merging ingested sources, or keeping the wiki consistent.
---

# Wiki maintainer

- Read **`llm-wiki/CLAUDE.md`** and **`wiki/index.md`** first.
- **`raw/`** is immutable except via `llm-wiki ingest`; you own **`wiki/`** only.
- After substantive edits, update **`wiki/index.md`** one-line entries when appropriate and append **`wiki/log.md`**.
- If `git.enabled` in `llm-wiki/config.json` and `git.include_diff_in_skill_context`, run `llm-wiki git diff` (vault root) for context (truncate if huge).

See `references/workflows.md` for ingest/query/lint outlines.

Optional: when invoking tools, you may inject a short persona block per `skills/references/context-persona.md` (vault display name: `persona.name` in `llm-wiki/config.json`, default **Gennie**).
