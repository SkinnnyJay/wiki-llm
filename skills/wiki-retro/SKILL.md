---
name: wiki-retro
description: Vault retrospective — activity, source mix, topic coverage, health, open questions, and recommendations from logs, git, and wiki-lint.
disable-model-invocation: true
---

# Wiki retro — Retrospective

Summarize **research velocity**, **source mix**, **topic coverage**, **wiki health**, and **open questions** from **`wiki/log.md`**, **`raw/.preparation-log.jsonl`** (if present), vault **git** history (if enabled), and a **wiki-lint**-style pass. Inspired by team retros (e.g. gstack `/retro`); output is **read-only analysis** plus optional updates to **`wiki-learn`** memory.

## Pre-flight

1. Confirm **`llm-wiki/config.json`** exists. Resolve vault root (default **`llm-wiki/`**).
2. If **`git.enabled`**, use **`llm-wiki git log`** / **`llm-wiki git lifecycle`** — not the parent repo’s `.git` for vault operations.

## Steps

### Step 1 — Activity summary

- Read **`wiki/log.md`**: count dated sections in the last 7 days (or window in `$ARGUMENTS`).
- Note lines matching **`research`**, **`ingest`**, **`pipeline`**, **`deep-research`**, etc.

### Step 2 — Source mix

- Scan **`raw/**/*.md`** (sample or full): group by `source_type`, `platform`, or path prefix (`raw/news/`, `raw/academic/`, …).
- If **`raw/.preparation-log.jsonl`** exists, count **`prepare`** / **`raw finish`** actions in the window.

### Step 3 — Topic coverage

- Read **`wiki/index.md`**: list sections or topics with most **new** vs **stale** pages (use **`wiki/log.md`** dates when available).

### Step 4 — Health

- Run **wiki-lint** logic (or invoke the skill): orphans, broken **`[[wikilinks]]`**, contradictions.
- Compare to **last retro** if **`outputs/retro-*.md`** exists: delta one-liners.

### Step 5 — Open questions

- Aggregate **`Open questions:`** bullets from **`wiki/log.md`** and lint gaps.

### Step 6 — Recommendations

- Propose next research topics, pages to refresh, or integrations to enable.
- Optionally append bullets under **`## Next Steps`** in **`llm-wiki/.agent-memory.md`** (**wiki-learn**).

### Step 7 — Write report

Save to **`outputs/retro-YYYY-MM-DD.md`** (create **`outputs/`** if missing):

1. **Activity summary** — sessions, ingests, wiki updates in window  
2. **Source mix** — breakdown by type/path  
3. **Topic coverage** — hot/cold areas  
4. **Health trend** — lint issues; delta vs last retro if known  
5. **Open questions** — collected list  
6. **Recommendations** — concrete next actions  

## Done looks like

- **`outputs/retro-YYYY-MM-DD.md`** exists with all six sections (use **N/A** where data is missing).
- User gets a short **executive summary** in chat plus path to the full report.
- If vault git was enabled, commit subjects by phase are referenced when useful.

## Artifacts

| Reads | Writes |
|-------|--------|
| `wiki/log.md`, `wiki/index.md`, `raw/**`, `raw/.preparation-log.jsonl`, optional `llm-wiki git log` | `outputs/retro-YYYY-MM-DD.md`, optional `llm-wiki/.agent-memory.md` **Next Steps** |

## Related skills

- **wiki-lint** — health signals  
- **wiki-learn** — persist recommendations  
- **wiki-status** — tooling/config snapshot  
- **wiki-pipeline** — standard flow for fixes  

## Smoke check

- **CLI:** From the vault root: `llm-wiki validate`; if vault git is enabled, `llm-wiki git log -n 5`.
- **Prompt:** Invoke this skill; confirm retro uses `wiki/log.md` / git history when available.

Optional: `persona.name` in config (default **Gennie**).
