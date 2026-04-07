---
name: wiki-research
description: Ad-hoc internet research on a user topic — plan sources, ingest into raw/, merge into wiki/, log progress. Not the same as wiki-research-loop (batch tasks from research-tasks.json).
---

# Wiki research (topic session)

**Naming:** This skill is **wiki-research** (ad-hoc **topic**). Use **wiki-research-loop** only for recurring **batch** runs from **`research_loop.tasks_file`** (e.g. HN, fixed URL lists).

## When to use

- User gives a **research question or topic** (not a predeclared JSON task list).
- You need to **discover URLs**, fetch with **`llm-wiki ingest`**, then **wiki-ingest** / **wiki-maintainer**.

## Progress and logging

Work in **visible steps** (brief status before/after each phase). Persist:

1. **`wiki/log.md`** — Append an entry for this session, e.g. `## [YYYY-MM-DD] research | <short topic>` with bullets: scope, sources ingested (paths under `raw/`), wiki pages touched, open questions.
2. **`raw/.preparation-log.jsonl`** — When you run **`wiki-raw-prepare`** / **`llm-wiki raw record`**, keep goals aligned with what you changed.

Optional vault git: **`llm-wiki git snapshot -m "…" --phase ingest`** after raw landings, **`--phase wiki`** after wiki merge (if `git.enabled`).

## Phases (follow in order)

1. **Scope** — Restate the topic and success criteria (what “done” looks like). If **`$ARGUMENTS`** is empty, infer from the user message.
2. **Plan sources** — List candidate URLs or search strategies. Prefer **`llm-wiki integrations status`** / config to see enabled tools (e.g. Firecrawl, Perplexity). Respect rate limits and site terms; do not scrape aggressively.
3. **Ingest** — For each chosen source, materialize into **`raw/`** with predictable paths, e.g. `raw/research/<topic-slug>/<source-slug>.md`. Use **`llm-wiki ingest url …`**, **`ingest hackernews`**, **`ingest file`**, or adapters listed by **`llm-wiki ingest --list`**. One primary source per file when possible (traceability).
4. **Prepare raw (if needed)** — Messy HTML/PDF/OCR → **wiki-raw-prepare** / **`llm-wiki raw validate`** / **`raw finish`** per vault rules.
5. **Merge into wiki** — **wiki-ingest** and **wiki-maintainer**: update **`wiki/index.md`**, cross-links, **`wiki/log.md`**. If **ingestion_security** flags a file, follow **wiki-ingest** / **`skills/wiki-ingest/references/prompt-injection-review.md`**.
6. **Report** — List files created/updated, unresolved gaps, and suggested follow-up research.

## Artifacts and layers

| Layer | Use |
|-------|-----|
| **`raw/`** | Evidence: fetched text, URLs noted in body or frontmatter. Do not delete provenance users expect. |
| **`wiki/`** | Curated synthesis with **`[[wikilinks]]`** and citations to **`raw/`** paths. |
| **`outputs/`** | Optional drafts or long scratch notes; promote to **`wiki/`** only after review (see vault **`CLAUDE.md`** / **`ETHOS.md`**). |

## When to split vs merge pages

- **New wiki page** — Distinct subtopic, reusable entity, or a page that would exceed quick scanning (~30s) with everything on one screen.
- **Split a long synthesis** — Hub page + child pages linked with **`[[wikilinks]]`**; keep one clear title per page.
- **Keep one raw file per fetched URL** when practical so citations stay stable.

## Related skills

- **wiki-ingest** — Merge **`raw/`** into **`wiki/`**.
- **wiki-maintainer** — Index, links, consistency.
- **wiki-raw-prepare** — Clean structurally broken markdown in **`raw/`**.
- **wiki-research-loop** — Batch tasks from **`research-tasks.json`**, not topic-led sessions.

Optional: **`skills/references/context-persona.md`** and **`persona.name`** in **`llm-wiki/config.json`** (default **Gennie**).
