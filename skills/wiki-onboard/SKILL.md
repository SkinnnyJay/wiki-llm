---
name: wiki-onboard
description: First-run router for a new or existing llm-wiki vault.
when_to_use: Use when a user is new to llm-wiki, asks how to get started, or is unsure whether to set up, configure, or diagnose a vault.
disable-model-invocation: true
---

# Wiki onboard

Use this brief conversational router before a first workflow. Do not edit files until the destination flow asks for confirmation.

## Vault path preamble

Never assume the vault is `Path("llm-wiki/")`. Use `llm-wiki doctor` to locate and diagnose the vault; for direct filesystem work, resolve `LLM_WIKI_VAULT` first and use the resolved root consistently.

1. Ask the questions in [references/questions.md](references/questions.md), one at a time as needed.
2. Route a missing vault or missing `config.json` to **`/llm-wiki:setup`**.
3. Route a healthy existing vault with desired setting changes to **`/llm-wiki:configure`**.
4. Route an existing vault with errors, uncertain setup, or a failed check to **`llm-wiki doctor`**. Explain that `--fix` creates only missing vault directories and restores safe blank defaults; it never deletes vault content or replaces secrets.
5. After setup or configuration, recommend `llm-wiki doctor` to confirm readiness.

## Quick terminal check

```bash
llm-wiki doctor
```

## Smoke check

- **CLI:** `llm-wiki doctor` from a project with a vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** Invoke this skill for a first-time user; confirm it asks routing questions and does not write files before the destination flow.
