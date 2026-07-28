---
name: wiki-status
description: Diagnose vault readiness, integrations, and configured capabilities. Use for status, health checks, or pre-research verification.
when_to_use: Use when a user asks whether a vault is ready, reports setup or integration trouble, or needs a pre-flight health check before research or ingest.
allowed-tools: Read Grep Glob Bash
---

# Wiki status — health dashboard

## Vault path preamble

Never inspect a bare `Path("llm-wiki/")`. Start with `llm-wiki doctor`, which resolves and validates the vault. If direct filesystem inspection is necessary, resolve `LLM_WIKI_VAULT` first and use that root consistently.

## Workflow

1. Run `llm-wiki doctor` for the deterministic vault diagnostic.
2. Run `llm-wiki integrations status` when integrations matter to the user’s task.
3. Report readiness and the smallest safe remediation for anything missing or degraded.
4. Offer **wiki-setup** for a missing or incomplete vault; do not change configuration during a status check.

## Progressive disclosure

Read [the dashboard checks](references/dashboard-checks.md) only for a full environment report, index/KG diagnosis, or explicit troubleshooting.

## Done looks like

- The user knows whether the resolved vault is ready.
- Issues identify their affected capability and an actionable next command.
- Secrets remain masked and no configuration changes are made.

## Related skills

- **wiki-setup** — initialize or complete the vault.
- **wiki-onboard** — route a new user to the right first action.

## Smoke check

- **CLI:** `llm-wiki doctor` (and `llm-wiki integrations status` when integrations matter).
- **Prompt:** Invoke this skill; confirm it reports readiness without changing `config.json`.
