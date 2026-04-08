---
name: wiki-maintainer
description: Maintains the LLM Wiki vault — index, log, cross-links, contradictions. Use when editing llm-wiki/wiki/, merging ingested sources, or keeping the wiki consistent.
---

# Wiki maintainer — Curator

You own the **curated layer** under **`llm-wiki/wiki/`**. Sources live in **`llm-wiki/raw/`** (immutable except via **`llm-wiki ingest`**). After substantive edits or merges, keep **`wiki/index.md`**, **`wiki/log.md`**, and **`[[wikilinks]]`** coherent.

## Pre-flight

1. Read **`llm-wiki/CLAUDE.md`** and **`wiki/index.md`** first.
2. If `git.enabled` and `git.include_diff_in_skill_context`, run **`llm-wiki git diff`** (vault root) for context (truncate if huge).

## Steps

### Step 1 — Reconcile index and pages

- Ensure **`wiki/index.md`** lists new or renamed topics (one-line entries when appropriate).
- Remove or update stale index lines when pages are deleted or moved.

### Step 2 — Cross-links and structure

- Add or fix **`[[wikilinks]]`** where it helps navigation; avoid orphan targets (create stubs or remove links).
- If two pages contradict, surface the conflict in **`wiki/log.md`** or a dedicated note — do not silently pick a winner without evidence.

### Step 3 — Log

- Append **`wiki/log.md`** with date, scope, and files touched for non-trivial maintenance passes.

## Done looks like

- **`wiki/index.md`** reflects actual **`wiki/**/*.md`** pages (no stale-only index lines for missing pages unless intentional stubs).
- Broken **`[[wikilinks]]`** to missing targets are **fixed or flagged**.
- **`wiki/log.md`** records meaningful maintenance when appropriate.
- If vault git is used, user knows whether to run **`llm-wiki git snapshot`** (per project convention).

## Artifacts

| Reads | Writes |
|-------|--------|
| `llm-wiki/CLAUDE.md`, `wiki/index.md`, `wiki/**/*.md` | `wiki/index.md`, `wiki/log.md`, `wiki/**/*.md` |

Downstream: **wiki-lint**, **wiki-pipeline** (validate stage). See **`skills/references/pipeline-artifacts.md`**.

## Related skills

- **wiki-ingest** — merge new `raw/` material into topic pages (often precedes maintainer pass).
- **wiki-lint** — orphans, contradictions, gaps.
- **wiki-raw-prepare** — clean messy `raw/` before merge when needed.
- **wiki-query** — read-only Q&A from wiki.

See `references/workflows.md` for ingest/query/lint outlines.

## Smoke check

- **CLI:** From the vault root: `llm-wiki validate` and, if vault git is enabled, `llm-wiki git status`.
- **Prompt:** Invoke this skill by name; confirm Pre-flight reads `llm-wiki/CLAUDE.md` and `wiki/index.md`.

Optional: `skills/references/context-persona.md` and `persona.name` in `llm-wiki/config.json` (default **Gennie**).
