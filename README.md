<p align="center">
  <img src="docs/assets/readme-banner.png" alt="llm-wiki" width="100%" />
</p>

# llm-wiki — Claude Code plugin

**Docs site (GitHub Pages):** enable Pages from the **`/docs`** folder on `main`, then open `https://<user-or-org>.github.io/<repo>/` — see [`docs/README.md`](docs/README.md). The landing page credits **inspiration** from [Karpathy’s *LLM Wiki* gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) and quotes Newton’s letter to Hooke (shoulders of giants).

Personal knowledge vault for [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview): **`llm-wiki/`** holds **`raw/`** (ingested sources), **`wiki/`** (your markdown), optional **`outputs/`** (generated briefings and drafts—review before treating as canonical), and **`CLAUDE.md`** (vault rules). Same “folders + text files” idea as a plain **raw/ wiki/ outputs/** layout, with plugin tooling on top. Optional **vault-scoped Git**, **static graph viewer** (`wiki/.og/`), **on-demand D3 graphs** in **`.tmp/llm-wiki-graph/`** (link view + knowledge clusters), **ingest adapters**, and **ingestion security** (heuristic prompt-injection scan).

**Cursor & OpenAI Codex:** see **[`AGENTS.md`](AGENTS.md)** for how each tool loads instructions (Claude Code vs [Cursor plugins](https://cursor.com/docs/plugins) vs [Codex `AGENTS.md` discovery](https://developers.openai.com/codex/guides/agents-md/)). This repo ships **[`rules/llm-wiki.mdc`](rules/llm-wiki.mdc)** (Cursor project rules; mirrored under **`.cursor/rules/`**), **[`.cursor-plugin/plugin.json`](.cursor-plugin/plugin.json)** (for [Cursor Marketplace](https://cursor.com/marketplace/publish) packaging alongside **`.claude-plugin/`**), plus **`commands/`** and **`bin/llm-wiki`**.

| You want… | Use |
|-----------|-----|
| Tool-specific wiring (Claude / Cursor / Codex) | [`AGENTS.md`](AGENTS.md) |
| Cursor rules (clone & open) | [`rules/llm-wiki.mdc`](rules/llm-wiki.mdc) |
| Full slash-command prompts | [`commands/`](commands/) (one `.md` per command) |
| Full skill instructions | [`skills/*/SKILL.md`](skills/) |
| Agent definitions | [`agents/`](agents/) |
| Plugin + agent **persona** (voice, epistemics) | [`prompts/PERSONA.md`](prompts/PERSONA.md), [`agents/wiki-librarian/persona.md`](agents/wiki-librarian/persona.md), [`agents/research-runner/persona.md`](agents/research-runner/persona.md) |
| Optional tool-calling persona hook | [`skills/references/context-persona.md`](skills/references/context-persona.md) |
| Canonical flows and troubleshooting | [`WORKFLOWS.md`](WORKFLOWS.md) |
| Builder principles (raw vs wiki, evidence) | [`ETHOS.md`](ETHOS.md) |

---

## Slash commands (`/llm-wiki:…`)

Invoked in Claude Code after loading the plugin. Each file under [`commands/`](commands/) is the source prompt; the table below is the short version.

| Command | What it does |
|---------|----------------|
| `/llm-wiki:setup` | Vault setup wizard — paths, `config.json`, optional git init. |
| `/llm-wiki:ingest` | Plan or run ingest: materialize into `raw/`, then merge into `wiki/` per skills. |
| `/llm-wiki:raw-prepare` | Validate/clean `raw/` markdown (CLI + LLM), log goals to `raw/.preparation-log.jsonl`, optional git `--phase prepare`. |
| `/llm-wiki:query` | Answer from the wiki with citations; optionally file the answer into `wiki/`. |
| `/llm-wiki:lint` | Health-check the wiki — orphans, gaps, contradictions. |
| `/llm-wiki:build-og` | Run `build-site`: emit `wiki-data.json` + static viewer under `wiki/.og/`. |
| `/llm-wiki:integrations` | Configure optional integrations (env vars, `integrations.*` in config). |
| `/llm-wiki:research` | Ad-hoc research on a **topic** — plan sources, ingest into `raw/`, merge into `wiki/`, stepped progress + `wiki/log.md` (**wiki-research** skill). |
| `/llm-wiki:research-loop` | **Batch** recurring tasks from `research-tasks.json` (path in config) when `research_loop.enabled` (**wiki-research-loop**). |
| `/llm-wiki:graph` | Build a **D3 link graph** from wikilinks into `.tmp/llm-wiki-graph/`; serve with `http.server`. |
| `/llm-wiki:graph-knowledge` | Same output folder, **knowledge view**: colors = undirected **connected components** (relational clusters). |
| `/llm-wiki:git-status` | Vault-only `git status` (requires `git.enabled`). |
| `/llm-wiki:git-log` | Vault-only log. |
| `/llm-wiki:git-diff` | Vault-only diff (working tree / staged). |
| `/llm-wiki:git-snapshot` | Commit vault state with a message. |
| `/llm-wiki:git-lifecycle` | Audit commits by **lifecycle phase** (prefix tags) — flow progression, JSON export. |

---

## Agent skills

In Claude Code, skills load when relevant; in Cursor/Codex, open **`skills/*/SKILL.md`** or follow the slash commands above (same workflows).

| Skill | What it does | When to use |
|-------|----------------|-------------|
| **wiki-maintainer** | Keeps `wiki/` coherent: index, log, cross-links, contradictions. | Editing `wiki/`, merging sources, consistency passes. |
| **wiki-ingest** | Merges `raw/` into `wiki/` with index/log updates; respects ingestion security sub-prompt when flagged. | After `llm-wiki ingest` or new files in `raw/`. |
| **wiki-query** | Answers using wiki pages with **citations** to file paths. | Questions about vault content. |
| **wiki-lint** | Audits orphans, broken wikilinks, stale claims, contradictions. | “Health check” or audit requests. |
| **wiki-research** | Topic-led research: discover sources, **`llm-wiki ingest`**, merge with **wiki-ingest** / **wiki-maintainer**, log phases in **`wiki/log.md`**. | User gives a research question or subject (not the JSON task file). |
| **wiki-research-loop** | Runs **batch** tasks from the research tasks file (`research_loop.tasks_file`, default `research-tasks.json`). | HN / fixed URL lists on a schedule when `research_loop.enabled`. |
| **wiki-raw-prepare** | Deterministic **`raw validate`** + LLM cleanup for HTML/PDF/OCR markdown; **`raw record`** audit log; aligns with git **`[prepare]`** phase. | After ingest when `raw/` is not yet valid markdown, before **wiki-ingest**. |

Security note for **wiki-ingest**: when `ingestion_security` flags content, follow `skills/wiki-ingest/references/prompt-injection-review.md`.

---

## Agents

| Agent | Role |
|-------|------|
| **wiki-librarian** | Large multi-file wiki edits, batch cross-links; prefers `llm-wiki git *` when `git.enabled`. |
| **wiki-raw-prepare** | Cleans and validates **`raw/`** before wiki merge; see [`agents/wiki-raw-prepare.md`](agents/wiki-raw-prepare.md). |
| **research-runner** | Long research passes (many URLs/HN items); uses ingest + wiki-ingest patterns. |

---

## CLI (`bin/llm-wiki`)

Ensure the plugin `bin/` is on your `PATH`, or run:

- **`bin/llm-wiki`** — use `./bin/llm-wiki …` from the repo, or **`/absolute/path/to/wiki-llm/bin/llm-wiki …` from any directory** (the wrapper resolves the repo from the script’s location).
- **`python3 scripts/llm_wiki.py`** — only works when your shell’s **current directory is the repository root** (the folder that contains `scripts/`). If you see `can't open file 'scripts/llm_wiki.py'`, `cd` to that root or use `bin/llm-wiki` with an absolute path instead.

You do not need `PYTHONPATH` (the script prepends `scripts/` to `sys.path`). **Avoid** `PYTHONPATH=scripts` (a relative entry): on Python 3.14+ it can crash during startup with `OSError: failed to make path absolute`. If you must set `PYTHONPATH`, use an absolute path, e.g. `PYTHONPATH="$PWD/scripts"`.

| Subcommand | Purpose |
|------------|---------|
| `configure` | Write `config.json` (flags or `-i` interactive). Set wiki display name: `--persona-name "…"` (stored as `persona.name`, default **Gennie**). |
| `setup` | Scaffold `llm-wiki/` from templates (`--root`, optional `--vault`). |
| `teardown` | Remove `wiki/.og/` or `--purge` the whole vault (with `--yes`). |
| `build-site` / `build-og` | Generate viewer + `wiki-data.json`. |
| `validate` | Check layout; `--wikilinks` fails on links to missing `.md` files. |
| `ingest` | `ingest --list`; `ingest <adapter> …` (e.g. `file`, `url`, `hackernews`). |
| `raw validate` | Structural markdown checks for a file under `raw/` (balanced fences, etc.); **`--autofix`** for safe deterministic fixes. |
| `raw record` | Append one audit line to **`raw/.preparation-log.jsonl`** (`--goal`, `--action validated|autofixed|llm_cleaned|noted`). |
| `raw finish` | **`raw finish <path> -m "…"`** — autofix + validate + preparation log + **`[prepare]`** git snapshot ( **`--skip-git`** to log only). |
| `integrations` | `status`, `validate`, or `wizard` (printed steps). |
| `research-loop` | Run tasks with `run: true` from `research_loop.tasks_file` (default **`research-tasks.json`**, no extra deps). Use `.yaml` tasks only with **`pip install pyyaml`**. Flags: `--dry-run`, `--task ID`, `--force`. |
| `graph` | Emit `graph-data.json` + static D3 UI to **`.tmp/llm-wiki-graph/`** (override with `--out`). Modes: `--mode links` (default, degree-colored) or `--mode knowledge` (link-component clusters). |
| `graph-knowledge` | Alias for `graph --mode knowledge`. |
| `git` | `init`, `status`, `log`, `diff`, `snapshot`, `query`, **`lifecycle`** (audit by phase; `--json`, `--phase`, `--since`). `snapshot -m "…" --phase wiki` prepends `[wiki]`. Optional **`snapshot_after_build`** after `build-site`. |
| `security scan <file>` | Print heuristic scan JSON (does not mutate the file). |

**Optional APIs:** set env vars as needed — e.g. `FIRECRAWL_API_KEY`, `PERPLEXITY_API_KEY` (see `llm-wiki integrations status`). Perplexity: `llm-wiki ingest perplexity "your question"` or `--prompt-file`.

**PDF ingest (`ingest pdf`):** install pip extras in a venv (recommended): `python3 -m venv .venv && .venv/bin/pip install -r requirements-optional.txt`. Scanned PDFs need **PyMuPDF** + system **Tesseract** (`brew install tesseract` on macOS). Text-only PDFs use **MarkItDown** (`markitdown[pdf]` in that file).

---

## Example: from zero to graph

```bash
# 1) Load plugin (development)
claude --plugin-dir /path/to/wiki-llm

# 2) Scaffold vault
llm-wiki setup --root .

# 3) Copy a note into raw/ and optionally pull HN top stories
llm-wiki ingest file ./README.md --out notes/readme-copy.md
llm-wiki ingest hackernews --limit 5 --out research/hn-sample.md

# Optional: batch tasks from research-tasks.json (enable research_loop, set a task run: true)
# llm-wiki research-loop --dry-run
# llm-wiki research-loop

# 4) In Claude: merge raw → wiki (skill wiki-ingest), then build viewer
llm-wiki build-site
cd llm-wiki/wiki/.og && python3 -m http.server 8765
# Open http://127.0.0.1:8765/

# 5) Optional: standalone graph in .tmp (good for comparing link structure / clusters)
llm-wiki graph-knowledge
cd .tmp/llm-wiki-graph && python3 -m http.server 8890
```

In chat you can drive the same flow with **`/llm-wiki:ingest`**, then **`/llm-wiki:build-og`**, and ask Claude to apply **wiki-ingest** / **wiki-maintainer** so new `raw/` files become proper `wiki/` pages with wikilinks.

---

## Install (Claude Code — no clone)

Add the GitHub repo as a **plugin marketplace**, then install **llm-wiki** (catalog name in [`marketplace.json`](marketplace.json) is `llm-wiki-local`):

```text
/plugin marketplace add https://github.com/wiki-llm/wiki-llm
/plugin install llm-wiki@llm-wiki-local
```

Update the marketplace after upstream changes: `/plugin marketplace update`. See [Discover and install plugins](https://docs.anthropic.com/en/discover-plugins) and [plugin marketplaces](https://docs.anthropic.com/en/docs/claude-code/plugin-marketplaces).

**Cursor & Codex:** **[`AGENTS.md`](AGENTS.md)**; Cursor picks up **`rules/*.mdc`** (see **`.cursor/rules/`**). **Claude Code** in Cursor: enable plugins and run the marketplace steps above.

## Install (development — clone)

```bash
claude --plugin-dir /path/to/wiki-llm
```

Reload plugins after changes: `/reload-plugins`

```bash
claude plugin validate
# or
/plugin validate
```

## Configuration

All toggles live in **`llm-wiki/config.json`**: `viewer` (including `open_file_scheme`, `og_base_url`), `integrations`, `git`, `research_loop`, `ingestion_security`, **`hooks.sound`**, and **`persona.name`** — the wiki’s display name (default **Gennie**), surfaced in the static viewer / graph titles and in skill prompts when using `skills/references/context-persona.md`.

**Sound hook (optional):** Set `hooks.sound.enabled` to `true` and `hooks.sound.command` to a JSON array of argv (e.g. macOS `["afplay", "/System/Library/Sounds/Glass.aiff"]`, or a wrapper script path as the first element). When enabled, the CLI runs the command after a successful **`llm-wiki ingest`** (`on_ingest`) and after a successful **`llm-wiki research-loop`** run that executed at least one task (`on_research_loop`). Inner ingests during a research loop do not repeat the ingest hook; use `on_research_loop` for one notification per batch. Failures in the hook are logged to stderr and do not fail the main command.

**Persona:** The plugin ships **[`prompts/PERSONA.md`](prompts/PERSONA.md)** (warm, evidence-first librarian-robot; no fluff; verify don’t trust; iterate). Each agent adds **[`agents/wiki-librarian/persona.md`](agents/wiki-librarian/persona.md)** and **[`agents/research-runner/persona.md`](agents/research-runner/persona.md)**. Skills may optionally inject **`skills/references/context-persona.md`** when invoking tools.

**Viewer:** after `build-site`, serve `wiki/.og/` over HTTP (not raw `file://`) so the browser can load `wiki-data.json`. The viewer can link **Open file** via `viewer.open_file_scheme` (`file`, `vscode`, `cursor`). The header uses **`persona.name`** from `wiki-data.json`. Rendered page bodies go through **DOMPurify**; git ledger lines are escaped.

**Ingest paths:** Adapter `--out` must stay under `raw/` (relative only); paths that escape `raw/` are rejected.

**Wikilinks:** Obsidian-style `[[Page]]` / `[[page.md|label]]`. General Markdown: [Markdown Guide](https://www.markdownguide.org/basic-syntax/).

**Workflows:** Step-by-step green path, research loop, and troubleshooting table → [`WORKFLOWS.md`](WORKFLOWS.md). Principles for evidence and layers → [`ETHOS.md`](ETHOS.md).

**Vault git & lifecycle:** With `git.enabled`, use **`llm-wiki git lifecycle`** to classify recent commits by prefix (`git.lifecycle.phases` in config). That gives an auditable trail of ingest → wiki → build-site → graph-style progression when you use consistent `[phase]` prefixes (including `git snapshot --phase wiki`). See [`commands/git-lifecycle.md`](commands/git-lifecycle.md).

## Using llm-wiki with gstack

[garrytan/gstack](https://github.com/garrytan/gstack) is an opinionated Claude Code skill stack (planning, review, QA, ship, browse, safety modes, and more). It targets **general repo and product workflow**; **llm-wiki** targets a **dedicated knowledge vault** (`llm-wiki/` with `raw/` + `wiki/` + ingest + viewers).

Use them **together** without duplicating scope:

- **llm-wiki** — Scaffold the vault, ingest into `raw/`, merge into `wiki/`, validate wikilinks, build the static wiki viewer and optional `.tmp` graph bundles, vault-scoped git, ingestion security.
- **gstack** — Run `/review`, `/qa`, `/ship`, `/investigate`, `/browse`, etc. on **your application repo** (including the repo that contains `llm-wiki/` if you commit the vault).

Install gstack per [their README](https://github.com/garrytan/gstack#install--30-seconds). Keep **vault-specific** work in llm-wiki skills/commands; use **gstack** when you need repo-wide code review, browser QA, or release automation. Neither replaces the other.

## Marketplace

See [`marketplace.json`](marketplace.json) for a local marketplace entry.

## License

MIT — see [LICENSE](LICENSE).
