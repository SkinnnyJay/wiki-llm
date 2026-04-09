---
name: wiki-lint
description: Audits llm-wiki/wiki for orphans, stale claims, missing links, and contradictions. Use when user asks to health-check the wiki.
allowed-tools: Read Grep Glob Bash
---

# Wiki lint — Auditor

Audit **`wiki/`** for **orphans**, **broken `[[wikilinks]]`**, **contradictions**, and **gaps**. For **`raw/`** that is still structurally broken **before** wiki merge, use **wiki-raw-prepare** / **`llm-wiki raw validate`** first; **wiki-lint** focuses on **`wiki/`** coherence.

## Pre-flight

1. Read **`wiki/index.md`** and scan **`wiki/**/*.md`** (or scope to paths the user named).
2. If **`outputs/`** exists, include drafts vs **`wiki/`** duplicate or conflicting claims in scope.

## Steps

### Step 1 — Index vs filesystem

- List **orphans**: pages not linked from **`wiki/index.md`** where you expect them listed (project convention from **`llm-wiki/CLAUDE.md`**).
- List **broken wikilinks**: targets that do not exist.

### Step 2 — Contradictions and gaps

- Note **contradictions** between pages about the same entity (different claims).
- Suggest **next sources** or **open questions** to resolve gaps.

### Step 3 — Outputs vs wiki

- If **`outputs/`** exists, flag **duplicate claims** or **contradictions** between **`outputs/`** and **`wiki/`** (treat outputs as drafts until promoted with evidence).

### Step 4 — Refresh site viewer

If auto-fixable edits were applied and **`viewer.enabled`** is not false in config:

```bash
llm-wiki build-site --if-stale
```

This rebuilds **`wiki/.og/`** only when wiki content is newer than the last build.

## Done looks like

- Deliverable is a **structured report**: orphans, broken links, contradictions, gaps — each with **concrete next actions** (create page, remove link, merge, research).
- **Auto-fixable** issues (if any) are fixed or listed with exact edits to apply.
- User knows whether the wiki is **ship-ready** for their use case or needs follow-up **wiki-research** / **wiki-maintainer** work.

## Artifacts

| Reads | Writes |
|-------|--------|
| `wiki/index.md`, `wiki/**/*.md`, optional `outputs/**` | Optional `outputs/lint-report.md` if the user wants a saved report |

Downstream: **wiki-maintainer** (fixes), **wiki-pipeline** (gate). See **`skills/references/pipeline-artifacts.md`**.

## Related skills

- **wiki-raw-prepare** — structural cleanup in **`raw/`** before merge.
- **wiki-maintainer** — apply cross-link and index fixes.
- **wiki-query** — Q&A from wiki after lint passes.
- **wiki-session-memory** — session memory files under **`raw/memory/`** (optional context).

## Smoke check

- **CLI:** From the vault root: `llm-wiki validate` and `llm-wiki validate --wikilinks` when testing wikilinks.
- **Prompt:** Invoke this skill; confirm the report structure (orphans, links, gaps) is produced.

Optional: `skills/references/context-persona.md` when running checks via tools; `persona.name` in config (default **Gennie**).
