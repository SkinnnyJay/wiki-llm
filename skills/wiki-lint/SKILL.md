---
name: wiki-lint
description: Audits llm-wiki/wiki for orphans, stale claims, missing links, and contradictions. Use when user asks to health-check the wiki.
when_to_use: When the user asks to audit wiki health, find orphans or broken wikilinks, run lint/compile gates, or check claims before shipping.
allowed-tools: Read Grep Glob Bash
---

# Wiki lint — Auditor

Audit **`wiki/`** for **orphans**, **broken `[[wikilinks]]`**, **contradictions**, and **gaps**. Prefer the deterministic CLI/MCP gates when available; use skill judgment for semantic contradictions the machine cannot see. For **`raw/`** that is still structurally broken **before** wiki merge, use **wiki-raw-prepare** / **`llm-wiki raw validate`** first; **wiki-lint** focuses on **`wiki/`** coherence.

## Pre-flight

1. Read **`wiki/index.md`** and scan **`wiki/**/*.md`** (or scope to paths the user named).
2. If **`outputs/`** exists, include drafts vs **`wiki/`** duplicate or conflicting claims in scope.
3. Run machine lint first (then deepen with this skill):

```bash
llm-wiki lint --write-report
# after wiki merge / before shipping:
llm-wiki compile --no-site
# surgical (pages citing one source):
llm-wiki compile --raw raw/path.md --no-site
```

MCP: **`wiki_lint`**, **`wiki_compile`** (same gates). Reports: **`outputs/lint-report.json`**, **`outputs/claims.json`**.

## Steps

### Step 1 — Index vs filesystem

- List **orphans**: pages not linked from **`wiki/index.md`** where you expect them listed (project convention from **`llm-wiki/CLAUDE.md`**).
- List **broken wikilinks**: targets that do not exist.
- Compare with **`llm-wiki lint`** / **`outputs/lint-report.json`** (`orphan`, `broken_wikilink`).

### Step 2 — Contradictions and gaps

- Note **contradictions** between pages about the same entity (different claims).
- Check **`llm-wiki kg conflicts`** and claim IR in **`outputs/claims.json`**.
- Suggest **next sources** or **open questions** to resolve gaps.

### Step 3 — Outputs vs wiki

- If **`outputs/`** exists, flag **duplicate claims** or **contradictions** between **`outputs/`** and **`wiki/`** (treat outputs as drafts until promoted with evidence).

### Step 4 — Refresh site viewer

If auto-fixable edits were applied and **`viewer.enabled`** is not false in config:

```bash
llm-wiki build-site --if-stale
# or fold into:
llm-wiki compile
```

This rebuilds **`wiki/.og/`** only when wiki content is newer than the last build.

## Done looks like

- Deliverable is a **structured report**: orphans, broken links, contradictions, gaps — each with **concrete next actions** (create page, remove link, merge, research).
- Machine gates (**`lint`** / **`compile`** / optional **`knowledge-test`**) are green or listed with fixes.
- User knows whether the wiki is **ship-ready** for their use case or needs follow-up **wiki-research** / **wiki-maintainer** work.

## Artifacts

| Reads | Writes |
|-------|--------|
| `wiki/index.md`, `wiki/**/*.md`, optional `outputs/**` | Prefer **`outputs/lint-report.json`** / **`claims.json`** via CLI; optional `outputs/lint-report.md` |

Downstream: **wiki-maintainer** (fixes), **wiki-pipeline** (gate). See **`skills/references/pipeline-artifacts.md`**. Shared config: **`skills/references/mcp-and-kg.md`** (`compile.*`, aliases, ontology).

## Related skills

- **wiki-raw-prepare** — structural cleanup in **`raw/`** before merge.
- **wiki-maintainer** — apply cross-link and index fixes.
- **wiki-query** — Q&A from wiki after lint passes.
- **wiki-session-memory** — session memory files under **`raw/memory/`** (optional context).

## Smoke check

- **CLI:** `llm-wiki lint --write-report`; `llm-wiki compile --no-site`; `llm-wiki knowledge-test --file examples/knowledge-tests.json` (plugin examples; scaffolded vaults pass).
- **Prompt:** Invoke this skill; confirm the report structure (orphans, links, gaps) is produced.

Optional: `skills/references/context-persona.md` when running checks via tools; `persona.name` in config (default **Gennie**).
