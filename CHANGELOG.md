<p align="center">
  <img src="docs/assets/readme-banner.png" alt="llm-wiki" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/SkinnnyJay/wiki-llm" title="Repository on GitHub"><img src="https://img.shields.io/badge/GitHub-repo-181717?logo=github&logoColor=white" alt="GitHub repo"/></a>
  &nbsp;
  <a href="https://github.com/SkinnnyJay/wiki-llm#install-claude-code" title="Install the plugin in Claude Code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-D4A574?logo=anthropic&logoColor=white" alt="Claude Code plugin"/></a>
  &nbsp;
  <a href="https://github.com/SkinnnyJay/wiki-llm/blob/main/AGENTS.md" title="AGENTS.md for Cursor and Codex"><img src="https://img.shields.io/badge/Cursor-rules%20%2B%20plugin-000000?logo=cursor&logoColor=white" alt="Cursor rules"/></a>
</p>


# Changelog

All notable changes to the llm-wiki plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions use [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Positioning** — Knowledge **compiler** framing: sources in → trusted agent-ready wiki out; demote session memory / web as optional; five-minute path ends at **search**.

### Security
- **MCP local ingest gate** — block all local-path adapters (`file`, `pdf`, `pdf-*`, `convo`) when `allow_local_file_ingest` is false (hyphenated IDs + convo).
- **`wiki_configure`** — empty allowlist also denies `hooks.*` (blocks sound-command RCE via MCP).
- **`wiki_read_page`** — restricted to `wiki/`, `raw/`, `outputs/` (no `config.json` / token reads).
- **`safe_fetch`** — fail closed when peer IP cannot be verified (override: `LLM_WIKI_SAFE_FETCH_ALLOW_MISSING_PEER`).
- **`apps/web`** — reject non-loopback `Host` / `X-Forwarded-Host` on API routes.

### Added
- **Safer vault template defaults** — MCP ingest/benchmark tools off; optional integrations off; `ingestion_security.block_on_suspected` true.
- **Agent CI L0** — retrieval smoke + baseline R@5; L2 skill-evals skip without secret.
- **CLI** — `--json` emit helpers; ASCII OK/FAIL; Windows launcher improvements.
- **Knowledge compiler CLI** — `lint`, `diff`, `compile`, `knowledge-test`; `validate --schema`; `kg conflicts`; wiki page provenance schema (`sources`, `confidence`, `stale_after`, …).
- **MCP** — `wiki_search` defaults to `scope=wiki` (compiled knowledge first).
- **Phase 4 compiler** — entity `knowledge_graph.aliases` on add/query/rebuild; light `allowed_predicates` ontology; claim IR → `outputs/claims.json`; surgical `compile --raw <path>`.
- **MCP knowledge CI** — `wiki_lint`, `wiki_compile`, `wiki_knowledge_test`; pytest job **Compile smoke** on a temp vault.
- **Compiler harden** — empty `--raw` scope no longer full-vaults; harden `normalize_raw_rel`; `mcp.compile_enabled` gate; doctor lint/claims/KG checks; `compile --stubs` → `outputs/stubs/` only; atomic lint/claims writes.

### Fixed
- Packaging honesty for `setup` when templates are absent from a wheel install.
- KG conflict CI ignores multi-valued structural predicates (`mentions`, `links_to`, …).

## [0.3.0] — 2026-07-28

Productionization release: application security, doctor/onboard DX, installable packaging, MCP protocol negotiation, and optional `apps/web`.

### Security
- **Vault paths** — reject path-escape attempts so file operations remain within the configured vault.
- **URL ingest** — `safe_fetch` validates destination addresses and redirect hops to mitigate SSRF.
- **MCP** — harden HTTP exposure with loopback and token controls; restrict configuration and write-capable tools; stdio binds `LLM_WIKI_VAULT` like SSE.
- **Indexes** — quarantine corrupt knowledge-graph and raw indexes rather than treating them as empty and overwriting them.
- **Ingest size caps** — bound download/body size for user-URL adapters.
- **Threat model + disclosure** — `docs/THREAT-MODEL.md`, `SECURITY.md`, `NOTICE`, light CoC / issue / PR templates.

### Added
- **`llm-wiki doctor [--fix]`** — vault health diagnostics with safe repairs; MCP `wiki_doctor`; slim **wiki-status** over doctor.
- **`/llm-wiki:onboard`** + **wiki-onboard** — first-run router to setup / configure / doctor.
- **CLI** — **`search`**, Windows **`bin/llm-wiki.cmd`**, **`teardown --artifacts`**, version SSOT via **`--version`**.
- **CLI** — **`build-site`** / **`build-og`**: **`--serve`**, **`--serve-background`**, **`--stop-serving`**, **`--port`**.
- **`apps/web`** — optional agent desk (tracked; typecheck CI); not part of the default plugin runtime.
- **Packaging** — installable wheel via `pyproject.toml`; CI empty-venv / wheel smoke (`pypi-smoke`).
- **Skill-evals workflow** — scheduled/manual credential-gated evals (`.github/workflows/skill-evals.yml`).
- **Session memory** — opt-in **`memory.*`**, **`llm-wiki memory …`**, MCP memory tools, hooks, **wiki-session-memory**.
- **`playwright` ingest adapter** — headless Chromium fetch to **`raw/`** with setup/wizard hints.

### Changed
- **MCP protocol** — advertise `2025-11-25`; retain `2024-11-05` for clients that explicitly negotiate that legacy revision. No future protocol date is advertised.
- **MCP layout** — split helpers under `scripts/mcp/` with lazy init (no import-time exit).
- **Skills** — lean setup/status bodies + references; `when_to_use`; SKILL-TEMPLATE invocation matrix; vault-path preamble.
- **Viewer** — mobile/a11y basics; vendor CDN + SRI where applicable.
- **Deps** — chromadb / pytest floors; ruff pre-commit bump; absolute `PYTHONPATH` in CI.
- **Docs** — front-door cleanup (README, INSTALL, CLI, CONFIGURATION, ARTICLE, QAPLAYBOOK); pre-ship checklist.

### Fixed
- **CLI** — bare `llm-wiki` (no subcommand) prints help and exits **0**.
- **CLI** — **`setup`** accepts **`--vault`** after the subcommand.
- **Session memory (hooks)** — Stop hook passes multiline assistant text via **`--message-preview-file`**.
- **Ingest** — **`hackernews`** single-item fetch, pacing, clearer HTTP errors.
- **Plugin MCP** — args use **`${CLAUDE_PLUGIN_ROOT}/scripts/mcp_server.py`**.
- **Claude Code plugin skills** — do not sync **`.claude/`** into the plugin root ([anthropics/claude-code#44120](https://github.com/anthropics/claude-code/issues/44120)).

## [0.2.0] — 2026-04-08

### Added
- `hooks/hooks.json` — hooks auto-load when plugin is installed (PreCompact, Stop)
- `settings.json` — sets wiki-librarian as default agent when plugin is enabled
- `.claude/rules/llm-wiki.md` — Claude Code rule discovery alongside existing `.mdc`
- `userConfig` in plugin.json for Firecrawl, Brave, and Perplexity API keys
- `argument-hint` on skills that accept user arguments
- `context: fork` + `effort: high` on wiki-pipeline, wiki-research-deep, wiki-research-loop
- `allowed-tools` on read-only skills (wiki-query, wiki-status, wiki-lint)
- Agent fields: `disallowedTools`, `color`, `memory`, `background`

### Changed
- **Agents restructured** — flattened from `agents/*/AGENT.md` to `agents/*.md` (Claude Code agent discovery requires flat files)
- **Persona inlined** — agent persona content moved from separate `PERSONA.md` files into agent markdown bodies
- **Hook scripts** — now resolve CLI via `${CLAUDE_PLUGIN_ROOT}/bin/llm-wiki` with PATH fallback
- **`marketplace.json`** moved from repo root to `.claude-plugin/` per official spec
- `.cursor-plugin/plugin.json` displayName changed to "LLM Wiki"
- `plugin.json` enriched with `homepage`, `author.url`, expanded `keywords`

### Removed
- Non-standard `triggers` frontmatter from all 32 skills (Claude Code only reads `description`)
- Nested agent directories (`agents/wiki-librarian/`, `agents/research-runner/`, `agents/wiki-raw-prepare/`)

### Fixed
- Skill descriptions trimmed to ≤250 characters to prevent truncation in Claude's skill listing
- Added `disable-model-invocation: true` to side-effect skills (extract-*, setup, pipeline, retro, upgrade, research-loop)
- Added `user-invocable: false` to internal sub-skills (research-academic/deep/feeds/news/social/web, raw-prepare, learn, extract-paywall)

## [0.1.13] — 2026-04-05

Initial plugin release with 32 skills, 3 agents, 16 commands, 2 hook scripts,
Python CLI, vault template, static viewer, and D3 graph bundle.
