# Skill template (llm-wiki)

Copy this structure when adding or overhauling a skill. Real skills live in `skills/<name>/SKILL.md` with YAML frontmatter.

```markdown
---
name: <skill-name>
description: <One-line purpose sentence, ≤250 chars. Front-load trigger keywords.>
when_to_use: <User intent, trigger phrases, and exclusions in one sentence.>
# Invocation matrix — choose one:
# User-invocable workflow / explicit slash command:
disable-model-invocation: true
# Agent-selected helper (omit disable-model-invocation):
# disable-model-invocation: false
---

# <Skill Name> — <Role Title>

<1–2 sentence overview of what this skill does and when to use it.>

## Vault path preamble (omit only for skills that never access a vault)

Never assume the vault is `Path("llm-wiki/")`. Prefer the `llm-wiki` CLI, which resolves the configured vault. If direct filesystem access is required, resolve `LLM_WIKI_VAULT` first; otherwise run `llm-wiki doctor` and ask the user to select or initialize a vault. Use the resolved root for every path.

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

## Invocation matrix

| Skill type | Frontmatter | How it runs |
|------------|-------------|-------------|
| User-invocable workflow | `disable-model-invocation: true` | A user explicitly invokes the slash command or names the skill. Use for setup, destructive actions, or workflows that require a user gate. |
| Agent-selected helper | Omit `disable-model-invocation` (or set it to `false`) | The model may select it when its `when_to_use` matches. Use for safe, composable capabilities. |

Do not pin model IDs in skill frontmatter. If a workflow forks and later stages depend on its result, set `background: false` so the gate can wait for completion.

## Progressive disclosure

Keep `SKILL.md` as the routing contract: frontmatter, iron rules, path preamble, short workflow, and links to references. Put adapter tables, exhaustive prompts, long scripts, examples, and troubleshooting in `references/`. Read a reference only when the selected path needs it; avoid loading every reference by default.

**Persona:** Reference **`prompts/PERSONA.md`** (do not inline it). For tool-heavy runs, point to **`skills/references/context-persona.md`** and `persona.name` in `llm-wiki/config.json` (default **Gennie**).
