# Changelog

All notable changes to the llm-wiki plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions use [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
