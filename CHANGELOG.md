# Changelog

## 0.1.13

- **Slash command:** **`/llm-wiki:research`** (`commands/research.md`) — ad-hoc topic research with stepped progress and **`wiki/log.md`** entries.
- **Skill:** **wiki-research** (`skills/wiki-research/SKILL.md`). Distinct from **wiki-research-loop** (batch **`research-tasks.json`**). Docs: **`README.md`**, **`WORKFLOWS.md`**, **`AGENTS.md`**, **`rules/llm-wiki.mdc`**, vault **`templates/llm-wiki/CLAUDE.md`**, **`agents/research-runner.md`**.

## 0.1.12

- **Vault template:** **`outputs/`** (with schema in **`CLAUDE.md`**) for generated answers and drafts; **`ETHOS.md`** notes compounding risk when promoting unreviewed text into **wiki/**. **wiki-query** / **`/llm-wiki:query`** can file to **outputs/** or **wiki/**.
- **Docs site (`docs/`):** Redesigned **`index.html`** + **`css/style.css`**; **Inspiration** (Newton quote with correct wording; [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)); **Goal**; **Setup** grid (Claude Code, Cursor, Codex/others, Obsidian); vault steps.
- **Cursor & Codex:** Root **`AGENTS.md`** (tool matrix + links to [Cursor plugins](https://cursor.com/docs/plugins), [Codex AGENTS.md](https://developers.openai.com/codex/guides/agents-md/)); canonical **`rules/llm-wiki.mdc`** with **`.cursor/rules/`** symlink; **`/.cursor-plugin/plugin.json`** for Cursor Marketplace packaging next to **`.claude-plugin/`**. README + docs site updated.
- **Docs:** Plugin persona moved from root **`persona.md`** to **`prompts/PERSONA.md`** (aligned with **`ETHOS.md`** / **`AGENTS.md`** naming; prompt-style text lives under **`prompts/`**).

## 0.1.11

- **Docs:** “Add to Claude Code (no clone)” via marketplace (`/plugin marketplace add` + `/plugin install llm-wiki@llm-wiki-local`); brief Cursor note on **`docs/index.html`** and README.

## 0.1.10

- **GitHub Pages:** Added **`docs/`** static site (About, Install, How to use) with **`docs/assets/logo.png`**, **`docs/css/style.css`**, **`docs/.nojekyll`**. Maintainer notes in **`docs/README.md`**.

## 0.1.9

- **Security:** Static wiki viewer sanitizes markdown HTML with **DOMPurify** before `innerHTML`; git **ledger** rows escape commit subjects/dates. **Ingest `--out`:** all adapters resolve output under `raw/` only (`lib.paths.raw_destination`) — rejects absolute paths and `..` escapes.

## 0.1.8

- **Ingest adapters:** `CONFIG_SCHEMA` on core adapters (`file`, `url`, `hackernews`, `youtube`) for documentation; **`llm-wiki integrations wizard`** prints each adapter’s schema and current `setup_checks`. **`scripts/ingest/README.md`** notes ingestion security + `security scan`.
- **Research loop:** Template **`templates/llm-wiki/research-tasks.yaml`** (same tasks as JSON); **`references/hn-example.md`** expanded (robots/ToS, external cron/Launchd/CI pattern, conservative limits).

## 0.1.7

- Optional **`hooks.sound`** in `config.json`: when `enabled`, run `command` (argv array) after successful **`llm-wiki ingest`** and after successful **`llm-wiki research-loop`** (one sound per batch; per-task ingests inside the loop do not trigger the ingest hook). Defaults are off; example uses macOS `afplay`.

## 0.1.6

- Vault git: **`llm-wiki git lifecycle`** classifies commits by `git.lifecycle.phases` prefixes; `--json`, `--phase`, `--since`. **`git snapshot -m "…" --phase wiki`** prepends the configured prefix. Config: optional `snapshot_after_build` (after `build-site`), and `lifecycle.phases` (defaults in template `config.json`). Tag graph work manually with `snapshot --phase graph` if you want it in the audit trail.

## 0.1.5

- Docs: `WORKFLOWS.md` (canonical vault flow + troubleshooting), `ETHOS.md` (raw vs wiki, evidence). README: “Using llm-wiki with gstack” (composable with https://github.com/garrytan/gstack).

## 0.1.4

- **Persona:** `prompts/PERSONA.md` (plugin), `agents/*/persona.md` (wiki-librarian, research-runner), optional `skills/references/context-persona.md` for tool-calling. Vault display name **`persona.name`** in `config.json` (default **Gennie**); `llm-wiki configure --persona-name` and interactive configure. Viewer + on-demand graph UIs show the name in titles via `wiki-data.json` / `graph-data.json`.

## 0.1.3

- On-demand **D3 graphs** into `./.tmp/llm-wiki-graph/`: `llm-wiki graph` (link/degree view) and `llm-wiki graph-knowledge` (connected-component clusters). Slash: `/llm-wiki:graph`, `/llm-wiki:graph-knowledge`. GitHub-dark–inspired theme; serve over HTTP like the main viewer.

## 0.1.2

- CLI: `research-loop` runs the research tasks file (`hackernews_top`, `fetch_urls`); default template is **`research-tasks.json`** (stdlib). YAML task files still supported with PyYAML.
- Ingest: **perplexity** adapter calls Perplexity `POST /v1/sonar` (`PERPLEXITY_API_KEY`).
- When `ingestion_security.llm_triage` is on and a scan flags suspected injection, print a reminder to review via wiki-ingest.

## 0.1.1

- Site: `wiki-data.json` includes `meta` (vault path, `open_file_scheme`, og base); viewer fixes D3 `forceLink` with object references; optional “Open file” link.
- CLI: `validate --wikilinks`, `integrations wizard`.
- Ingest: `hackernews` adapter `--depth comments` with `--comment-limit`.

## 0.1.0

- Initial Claude Code plugin: vault scaffold, `llm-wiki` CLI, ingest adapters (file, url), optional adapters (stubs), `build-site` viewer, vault-scoped git, research-loop skill, ingestion security scan.
