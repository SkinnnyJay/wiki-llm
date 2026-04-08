---
name: wiki-learn
description: Cross-session memory for the vault — learn, recall, and review patterns, preferences, pitfalls, and next steps in llm-wiki/.agent-memory.md.
user-invocable: false
---

# Wiki learn — Memory

Persist **patterns**, **preferences**, **pitfalls**, and **next steps** across sessions in a single human-reviewable file: **`llm-wiki/.agent-memory.md`**. Plain Markdown (no DB). Optional: integrate with **wiki-retro** (recommendations → **Next Steps**).

## Pre-flight

1. Ensure **`llm-wiki/`** exists. If **`.agent-memory.md`** is missing, create it from the template below (or append sections to an existing file).

### Initial file template

```markdown
# Agent memory (llm-wiki)

Optional cross-session notes. Edit freely. This file is **not** evidence for claims in `wiki/` — use `raw/` + `wiki/` for that.

## Research Patterns

## Preferences

## Pitfalls

## Next Steps
```

## Operations (from `$ARGUMENTS` or user message)

| Mode | Action |
|------|--------|
| **learn** | Append a dated bullet under the right section: `YYYY-MM-DD — <note> (context: …)` |
| **recall** | Read the file and surface entries relevant to the current task or query |
| **review** | Show all sections; offer to prune, merge, or move items to **`wiki/log.md`** if they become project decisions |

## Steps

### Step 1 — Classify the note

- **Research Patterns** — what source combos work, domains to avoid, query tricks  
- **Preferences** — tone, page structure, PDF adapter choice, automation level  
- **Pitfalls** — repeated failures (rate limits, paywalls, bad extractions)  
- **Next Steps** — follow-up topics (often fed by **wiki-retro**)

### Step 2 — Read or write

- **learn:** append; do not duplicate identical bullets unless reinforcing  
- **recall:** quote 3–7 most relevant lines for the user’s question  
- **review:** full file, then ask what to delete or rewrite  

### Step 3 — Integration

- **wiki-research** pre-flight: optionally **recall** Pitfalls + Preferences before classifying the request (see **wiki-research** — add one line “Read `.agent-memory.md` if present”).  
- **wiki-retro:** may append **Recommendations** to **Next Steps** here.

## Done looks like

- **learn:** new bullet(s) visible under the correct section with date.  
- **recall:** user sees relevant memory without dumping the whole file unless **review**.  
- **review:** user confirms edits or leaves file as-is.

## Artifacts

| Reads | Writes |
|-------|--------|
| `llm-wiki/.agent-memory.md` | `llm-wiki/.agent-memory.md` |

## Related skills

- **wiki-research** — consumes recall at session start (optional)  
- **wiki-retro** — feeds **Next Steps**  
- **wiki-pipeline** — may read memory before long runs  

## Smoke check

- **CLI:** `llm-wiki validate` from the vault root (vault must exist).
- **Prompt:** Invoke this skill; confirm learn/recall targets `llm-wiki/.agent-memory.md` when relevant.

Optional: `persona.name` in config (default **Gennie**).
