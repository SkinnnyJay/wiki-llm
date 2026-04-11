# Skill template (llm-wiki)

Copy this structure when adding or overhauling a skill. Real skills live in `skills/<name>/SKILL.md` with YAML frontmatter.

```markdown
---
name: <skill-name>
description: <One-line purpose sentence, ≤250 chars. Front-load trigger keywords.>
---

# <Skill Name> — <Role Title>

<1–2 sentence overview of what this skill does and when to use it.>

## Pre-flight (omit if N/A)

<Checks: config exists, required tools/keys, vault state. Point to `skills/references/preflight.md` if applicable.>

## Steps

### Step 1 — <verb phrase>

### Step 2 — …

## Done looks like

<Explicit success criteria: what files changed, what the user should see, pass/fail.>

## Artifacts

<What this skill reads and writes. Which downstream skill consumes the output. See `skills/references/pipeline-artifacts.md` for the vault pipeline.>

## Related skills

- **wiki-…** — …

```

**Persona:** Reference **`prompts/PERSONA.md`** (do not inline it). For tool-heavy runs, point to **`skills/references/context-persona.md`** and `persona.name` in `llm-wiki/config.json` (default **Gennie**).
