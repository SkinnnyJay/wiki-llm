---
description: First-run guide — choose setup, configuration, or vault diagnostics.
---

# Onboard — get a vault ready

Use **wiki-onboard** for a first run. It asks a few routing questions and sends the user to the right next step:

- New vault or missing `config.json` → **`/llm-wiki:setup`**
- Existing vault needing settings changes → **`/llm-wiki:configure`**
- Existing vault that may be broken → **`llm-wiki doctor`** (use `--fix` only for safe directory/default repairs)

Read `skills/wiki-onboard/SKILL.md` and follow its question flow.

## Arguments

$ARGUMENTS
