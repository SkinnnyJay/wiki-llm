# CLI (`llm-wiki`)

Use the CLI for terminals, CI, and automation. For the first vault setup, use the [five-minute quickstart](./QUICKSTART.md).

## Entrypoint

Run `bin/llm-wiki` from the plugin repo (or by absolute path from any directory), or run `python3 scripts/llm_wiki.py` from the repository root. Do not use a relative `PYTHONPATH=scripts`; the entrypoint sets its import path itself.

Use `llm-wiki --help` and `llm-wiki <command> --help` for flags.

## Commands

| Area | Commands |
|---|---|
| Vault lifecycle | `setup`, `configure`, `validate`, `check`, `teardown`, `wake-up`, `list-topics` |
| Content | `ingest`, `raw validate`, `raw record`, `raw finish`, `raw rebuild-index`, `security scan` |
| Viewer and graphs | `build-site` (`build-og` alias), `graph`, `graph-knowledge` |
| Agent integration | `mcp` (including `install` and `start`), `memory save\|log\|list\|show\|recall\|prune` |
| Knowledge and retrieval | `kg add\|query\|invalidate\|timeline\|stats\|rebuild`, `benchmark`, `metrics` |
| Operations | `git`, `integrations`, `deps`, `research-loop` |
| Plugin maintenance | `sync-agent-docs`, `smoke-test`, `test-report` |

`memory` is available when `memory.enabled` is set in the vault configuration. `mcp` starts stdio JSON-RPC by default and supports HTTP with `--transport sse`; see [`skills/references/mcp-and-kg.md`](../skills/references/mcp-and-kg.md).

## `doctor` and `onboard`

The current CLI does not implement `doctor` or `onboard`. Use `check` for fast vault or plugin sanity checks, and `setup` for first-time vault scaffolding.

## Related docs

- [`QUICKSTART.md`](./QUICKSTART.md) — first commands.
- [`WORKFLOWS.md`](../WORKFLOWS.md) — end-to-end flows and troubleshooting.
- [`SLASH-COMMANDS.md`](./SLASH-COMMANDS.md) — Claude Code command mapping.
