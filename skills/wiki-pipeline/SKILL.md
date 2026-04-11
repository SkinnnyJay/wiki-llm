---
name: wiki-pipeline
description: End-to-end vault workflow — status, research/fetch, raw prepare, wiki ingest, lint, build-site, validate — with optional user gates between stages.
disable-model-invocation: true
argument-hint: "[full | from raw | from wiki | status only]"
context: fork
agent: general-purpose
effort: high
---

# Wiki pipeline — Orchestrator

Run the standard **llm-wiki** path: **Source → Ingest → Prepare → Maintain → Build → Validate**, with explicit **gates** where the user can review before continuing. This is **domain-specific** to the vault.

See **`skills/references/pipeline-artifacts.md`** for what each stage writes and what reads it.

## Pre-flight

1. Run **wiki-status** (or the pre-flight snippet in **wiki-research**). If **`_meta.setup_completed`** is false, stop and offer **wiki-setup**.
2. Optionally read **`llm-wiki/.agent-memory.md`** if **wiki-learn** is in use; if **`memory.enabled`**, optionally **`llm-wiki memory recall`** for relevant past sessions (**wiki-session-memory**).

## Entry point (`$ARGUMENTS`)

Parse the user request:

| User says | Start at |
|-----------|----------|
| (default) / “full run” | **status** → research → … → validate |
| “from raw” / “merge only” | **prepare** (if needed) → **ingest** → … |
| “from wiki” / “lint and ship” | **lint** → **build** → **validate** |
| “status only” | **status** only |

Stages are **skipped** when not applicable (e.g. no new `raw/` files → skip prepare if user confirms raw is already clean).

## Stage map

| Order | Stage | Invoke | Gate (pause for user?) |
|------:|-------|--------|-------------------------|
| 1 | **status** | **wiki-status** | **Stop** if vault missing or setup incomplete |
| 2 | **research** | **wiki-research** (topic/URL) or **wiki-fetch** (quick URL) | **Gate:** “N file(s) in `raw/`. Review before wiki merge?” — skip auto-continue if user wants to inspect |
| 3 | **prepare** | **wiki-raw-prepare** / `llm-wiki raw validate` / `raw finish` | Usually no gate if validation passes |
| 4 | **ingest** | **wiki-ingest** then **wiki-maintainer** | **Gate:** “Updated wiki pages: …. Run lint?” (or auto-continue if user asked for full unattended run) |
| 4b | **kg update** | `llm-wiki kg rebuild` (if `knowledge_graph.auto_update_on_ingest`) | No gate — runs automatically after ingest |
| 5 | **lint** | **wiki-lint** | **Gate** if issues found: list orphans/contradictions; offer fixes via **wiki-maintainer** before build |
| 6 | **build** | `llm-wiki build-site` | No gate on success |
| 7 | **validate** | `llm-wiki validate` and `llm-wiki validate --wikilinks` if wiki has links | **Done** |

**Unattended mode:** If the user says “run all” / “no stops”, only stop on **status** failure or **validate** failure; log gate decisions as skipped in **`wiki/log.md`**.

## Steps (agent execution)

### Step 1 — Status

Run **wiki-status** integration + config checks. If setup is incomplete, offer **wiki-setup** and stop.

### Step 2 — Research / fetch (if needed)

If the user supplied a topic, URL, or batch intent, run **wiki-research** or **wiki-fetch** per **wiki-research** dispatch rules. After new files land in **`raw/`**, apply **gate** unless unattended.

### Step 3 — Prepare raw (if needed)

For messy HTML/PDF/OCR: **wiki-raw-prepare** + `llm-wiki raw finish` as in **wiki-raw-prepare**. If **`raw validate`** already passes with no LLM cleanup needed, skip. **`raw/`** validation skips **`raw/memory/`** (machine-generated session files).

### Step 4 — Wiki ingest

Run **wiki-ingest** then **wiki-maintainer**. Append **`wiki/log.md`** with a **`pipeline | …`** entry. **Gate** unless unattended.

If **`knowledge_graph.auto_update_on_ingest`** is true, run `llm-wiki kg rebuild` after wiki merges; the CLI also runs **`kg rebuild`** after **`post_ingest`** on new `raw/` files — see **`skills/references/mcp-and-kg.md`** § "KG auto-update after ingest".

### Step 5 — Lint

Run **wiki-lint**. If issues exist, **gate**: propose fixes or run **wiki-maintainer** / new pages.

### Step 6 — Build site

```bash
llm-wiki build-site
```

### Step 7 — Validate

```bash
llm-wiki validate
llm-wiki validate --wikilinks   # when wiki has wikilinks
```

Report pass/fail clearly.

## Done looks like

- Each executed stage completed or explicitly skipped with a one-line reason.
- **`wiki/log.md`** records the pipeline run (date, stages, notable files).
- **validate** exits successfully (or user accepts documented failures as follow-up).
- User knows where **`wiki/.og/`** is and how to serve it (see **WORKFLOWS.md**).

## Artifacts

Reads: **`llm-wiki/config.json`**, **`raw/`**, **`wiki/`**.  
Writes: per **pipeline-artifacts** table; pipeline primarily **orchestrates** other skills.

## Related skills

- **wiki-status**, **wiki-research**, **wiki-fetch**, **wiki-raw-prepare**, **wiki-ingest**, **wiki-maintainer**, **wiki-lint**
- **wiki-learn** — optional memory at start
- **wiki-retro** — periodic review of vault activity

## Smoke check

- **CLI:** From the vault root: `llm-wiki validate` and `llm-wiki build-site` as appropriate to the pipeline stage under test.
- **Prompt:** Invoke this skill; confirm pipeline stages are executed or skipped with a stated reason.

Optional: `skills/references/context-persona.md`; `persona.name` in config (default **Gennie**).
