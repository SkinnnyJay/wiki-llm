---
name: wiki-setup
description: Interactive vault setup wizard that previews configuration before scaffolding. Use for setup, initialization, or guided configuration.
when_to_use: Use when a user needs a new vault, wants guided initial configuration, or explicitly invokes /llm-wiki:setup; use wiki-configure for a narrow setting change.
disable-model-invocation: true
---

# Wiki setup — interactive wizard

**Iron rule:** Never write `config.json`, scaffold files, set environment variables, or initialize Git until the user explicitly confirms the final preview.

## Vault path preamble

Never use a bare `Path("llm-wiki/")`. Prefer `llm-wiki` CLI commands so the vault is resolved consistently. For direct filesystem work, resolve `LLM_WIKI_VAULT`; if it is unavailable, run `llm-wiki doctor` and ask the user to select or initialize the vault.

## Workflow

1. Determine whether the user wants a full setup, vault-only setup, or memory-only setup.
2. Confirm the current state with `llm-wiki doctor`; memory-only requires an existing vault.
3. Ask only the configuration questions needed for that route.
4. Show the complete effective configuration and proposed filesystem changes.
5. Apply only after confirmation, then suggest `llm-wiki doctor` and `llm-wiki integrations status`.

## Progressive disclosure

Use [the setup wizard runbook](references/setup-wizard.md) for question groups, backend choices, and apply details. Use [`docs/QUICKSTART.md`](../../docs/QUICKSTART.md) for the unattended defaults path.

## Done looks like

- The user approved a preview and the selected vault is initialized with the intended configuration.
- A cancellation leaves configuration and filesystem state unchanged.

## Related skills

- **wiki-status** — verify readiness after setup.
- **wiki-onboard** — route a first-time user to setup, configuration, or diagnosis.

## Smoke check

- **CLI:** `llm-wiki setup --help` (and `llm-wiki doctor` after a confirmed setup).
- **Prompt:** Invoke this skill; confirm it shows a full config preview and waits for explicit confirmation before writing.
