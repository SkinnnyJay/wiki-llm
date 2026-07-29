# CLI (`llm-wiki`)

Use the CLI for terminals, CI, and automation. For the first vault setup, use the [five-minute quickstart](./QUICKSTART.md).

## Entrypoint

Run `bin/llm-wiki` from the plugin repo (or by absolute path from any directory), or run `python3 scripts/llm_wiki.py` from the repository root. Do not use a relative `PYTHONPATH=scripts`; the entrypoint sets its import path itself.

Use `llm-wiki --help` and `llm-wiki <command> --help` for flags.

## Commands

| Area | Commands |
|---|---|
| Vault lifecycle | `setup`, `configure`, `validate`, `lint`, `diff`, `compile`, `knowledge-test`, `doctor`, `check`, `teardown`, `wake-up`, `list-topics` |
| Content | `ingest`, `search`, `raw validate`, `raw record`, `raw finish`, `raw rebuild-index`, `security scan` |
| Viewer and graphs | `build-site` (`build-og` alias), `graph`, `graph-knowledge` |
| Agent integration | `mcp` (including `install` and `start`), optional `memory …` |
| Knowledge and retrieval | `kg add\|query\|invalidate\|timeline\|stats\|rebuild\|conflicts`, `benchmark`, `metrics` |
| Operations | `git`, `integrations`, `deps`, `research-loop` |
| Plugin maintenance | `sync-agent-docs`, `smoke-test`, `test-report` |

`memory` is available when `memory.enabled` is set in the vault configuration. `mcp` starts stdio JSON-RPC by default and supports HTTP with `--transport sse`; see [`skills/references/mcp-and-kg.md`](../skills/references/mcp-and-kg.md).

## `doctor`

`llm-wiki doctor` diagnoses vault health (layout, config, readiness). Pass `--fix` to apply **safe** repairs only: create missing vault/`raw`/`wiki` directories and fill safe blank config defaults. It does not delete vault content or replace secrets.

Use `check` for a faster vault or plugin sanity pass (config + optional compileall) when you do not need the full doctor report.

## `lint` / `diff` / `compile` / `knowledge-test`

Knowledge compiler CI:

- **`lint`** — orphans, broken wikilinks, optional schema/stale/`review_required`; extracts claim IR to `outputs/claims.json` when `compile.extract_claims`; `--write-report` → `outputs/lint-report.json`
- **`diff --since HEAD~1`** — wiki/.kg path changes since a git ref
- **`compile`** — validate + lint + KG rebuild/conflicts + optional site (does **not** auto-write topic pages); **`compile --raw raw/foo.md`** limits lint/claims to pages citing that source
- **`knowledge-test --file examples/knowledge-tests.json`** — claim regression tests against `wiki/`
- **`kg conflicts`** — semantic (s,p) multi-object conflicts (skips multi-valued `mentions`/`links_to`)
- **Entity merge** — set `knowledge_graph.aliases` (e.g. `{"OAuth2":"OAuth"}`) so add/query/rebuild canonicalize labels
- **Ontology** — non-empty `knowledge_graph.allowed_predicates` rejects unknown predicates on `kg add` (builtins included unless `ontology_strict`)

## `search`

`llm-wiki search "<query>"` searches vault content using the configured MCP search backend (`mcp.search_backend`: fts5 / grep / chromadb / hybrid). Useful flags: `--limit`, `--tag`, `--scope {all,wiki,raw,memory}`.

## Onboard (slash / skill only)

There is **no** `llm-wiki onboard` CLI command. First-run routing is **`/llm-wiki:onboard`** (prompt [`commands/onboard.md`](../commands/onboard.md)) and the **wiki-onboard** skill. Those send new users to setup, configure, or `llm-wiki doctor` as appropriate.

## Related docs

- [`QUICKSTART.md`](./QUICKSTART.md) — first commands.
- [`WORKFLOWS.md`](../WORKFLOWS.md) — end-to-end flows and troubleshooting.
- [`SLASH-COMMANDS.md`](./SLASH-COMMANDS.md) — Claude Code command mapping.
