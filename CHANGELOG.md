<p align="center">
  <img src="docs/assets/readme-banner.png" alt="llm-wiki" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/SkinnnyJay/wiki-llm"><img src="https://img.shields.io/badge/GitHub-repo-181717?logo=github&logoColor=white" alt="GitHub repository"/></a>
  <a href="https://github.com/SkinnnyJay/wiki-llm#install-claude-code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-D4A574?logo=anthropic&logoColor=white" alt="Claude Code: install instructions"/></a>
  <a href="https://github.com/SkinnnyJay/wiki-llm/blob/main/AGENTS.md"><img src="https://img.shields.io/badge/Cursor-rules%20%2B%20plugin-000000?logo=cursor&logoColor=white" alt="Cursor: AGENTS.md"/></a>
</p>


# Changelog

All notable changes to the llm-wiki plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions use [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **CLI** — **`build-site`** / **`build-og`**: **`--serve`**, **`--serve-background`** (records PID in **`wiki/.og/.viewer-http.pid`**), **`--stop-serving`**, **`--port`**; preview the static viewer over HTTP without a separate **`cd`** + **`http.server`** step.
- **`playwright` ingest adapter** — Headless Chromium fetch to **`raw/`** (same markdown shape as **`url`** / Firecrawl); **`setup_checks`** + wizard hint when the Python package or browsers are missing; **`integrations wizard`** prints install hints for adapters with no API key (**`scripts/ingest/adapters/web_playwright.py`**, **`scripts/cli/core_commands.py`**).
- **Docs** — **`commands/ingest.md`**, **`commands/integrations.md`**, **`skills/wiki-fetch`**, **`wiki-ingest`**, **`wiki-setup`** (Section 4 + Section 8), **`wiki-status`**, **`commands/setup.md`**, **`docs/ENV.md`**: **`llm-wiki ingest playwright`** vs optional **Playwright MCP** (editor) vs vault **`llm-wiki` MCP**.

### Changed
- **`commands/ingest.md`** — Claude-facing **playbook** (slash table, phased checklist, **show steps**, **`2>&1`** for stderr); plus **adapter-agnostic** whole-web principles (APIs vs pages, limits, provenance, security, **improve each run**); example table (**`url`**, **`hackernews`**, **`file`**, **`ingest --list`**); playbook step 1 names **source type** and generic risks.
- **`skills/wiki-ingest/SKILL.md`** — **Learn from each merge**: log adapter/flags lessons, generalize patterns to **`wiki/log.md`** / vault **`CLAUDE.md`**; description notes any web/local source.
- **Claude Code dev docs** — document **`claude --plugin-dir`** as the usual one-off dev load again (current CLI); marketplace install remains the persistent option. **`tests/conftest.py`** and **`scripts/qa_record.py`** always pass **`--plugin-dir`** (removed the **`claude --help`** probe).
- **`scripts/plugin_dev_slim.sh`** — dry-run / **`--apply`** helper before local **`plugin install`** (local installs copy the full tree; not `.gitignore`-aware). **`setup`** warns if **`.claude/`** exists in the repo. **`.gitignore`** — common tool caches (**`.mypy_cache/`**, **`.ruff_cache/`**, etc.).

### Fixed
- **CLI** — Invoking **`llm-wiki`** with **no subcommand** (e.g. bare probe when **`bin/`** is on PATH from the Claude plugin) prints top-level help and exits **0** instead of argparse error **2**.
- **CLI** — **`setup`** accepts **`--vault`** after the subcommand (e.g. **`llm-wiki setup --root … --vault …`**), not only the global **`llm-wiki --vault … setup …`** form.
- **Session memory (hooks)** — Stop hook writes **`last_assistant_message`** to a **temp file** and passes **`--message-preview-file`** to **`memory log`** so multiline text, **quotes**, and **box-drawing** characters are not mangled by shell argv (fixes truncated or corrupted **`raw/memory/*.md`** rounds).
- **Ingest** — **`hackernews`**: optional **item id/URL** for a single story; **stderr progress** + **request pacing**; clearer **HTTP errors**; note that **`topstories.json`** order can **differ from the website** front page.
- **Plugin MCP** — **`mcpServers.llm-wiki.args`** now uses **`${CLAUDE_PLUGIN_ROOT}/scripts/mcp_server.py`** (Claude Code expects plugin paths via **`${CLAUDE_PLUGIN_ROOT}`**; a bare **`scripts/mcp_server.py`** often failed when the MCP process cwd was not the plugin root).
- **Claude Code plugin skills** — stop syncing agent rules to **`.claude/rules/`** inside the plugin repo. A **`.claude/`** directory in a plugin prevents discovery of root **`skills/`** ([anthropics/claude-code#44120](https://github.com/anthropics/claude-code/issues/44120)); use **`rules/llm-wiki.mdc`** + **`AGENTS.md`** / **`CLAUDE.md`** only.
- **`.gitignore`** — ignore **`.claude/`** under the plugin repo so local **`settings.local.json`** cannot sit next to **`skills/`** and block plugin discovery.

### Added
- **Session memory** — opt-in **`memory.*`** config, **`llm-wiki memory {save|log|list|show|recall|prune}`**, MCP tools (`memory_save`, `memory_list`, `memory_show`, `memory_recall`, `memory_prune`), search scope **`memory`**, hooks **`llm_wiki_memory.sh`** (Stop / PostCompact / SessionEnd), **`wiki-session-memory`** skill, **`commands/memory.md`**, **`raw/memory/`** excluded from raw prepare validation scans

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
