# llm-wiki workflows

**First run:** [`docs/QUICKSTART.md`](docs/QUICKSTART.md) — vault vs plugin repo, five-minute path, tier table (basic → advanced).

Canonical paths through the vault. Voice and epistemics: [`prompts/PERSONA.md`](prompts/PERSONA.md). Principles: [`ETHOS.md`](ETHOS.md).

**Cursor / OpenAI Codex (no Claude Code plugin):** [`AGENTS.md`](AGENTS.md) (how each tool loads this repo) — use **`bin/llm-wiki`** from a terminal, **`rules/llm-wiki.mdc`** / **`.cursor/rules/`** in Cursor, and **`commands/*.md`** for the same prompts as **`/llm-wiki:…`** slash commands.

**Quick install (plugin repo):** `./setup` from this repository prints next steps and verifies the CLI.

## Vault pipeline (orchestrated)

Optional **wiki-pipeline** skill chains the standard vault workflow with optional user gates: **status → research/fetch → raw prepare → wiki ingest → lint → build-site → validate**. See [`skills/wiki-pipeline/SKILL.md`](skills/wiki-pipeline/SKILL.md). Feed-forward artifacts between stages: [`skills/references/pipeline-artifacts.md`](skills/references/pipeline-artifacts.md).

**MCP (agents):** `llm-wiki mcp` — stdio JSON-RPC MCP server for editor-hosted agents. `llm-wiki mcp --transport sse` — HTTP POST JSON-RPC on `127.0.0.1` and `mcp.port` (default `8891`). Search backends and KG: **`skills/references/mcp-and-kg.md`**. After `ingest` post-processing, **`knowledge_graph.auto_update_on_ingest`** triggers a **KG rebuild** from wiki/raw markdown (wikilinks + tags).

- **wiki-retro** — periodic activity/health report to `outputs/retro-YYYY-MM-DD.md`.
- **wiki-learn** — cross-session notes in `llm-wiki/.agent-memory.md`.
- **wiki-session-memory** — opt-in per-chat notes in `llm-wiki/raw/memory/` (`memory.enabled`); hooks + `llm-wiki memory …`.
- **wiki-upgrade** — `git pull` + re-run `./setup` in the plugin repo.

## Retrieval benchmarks (plugin repo)

**CLI:** `llm-wiki benchmark …` — see [`benchmarks/README.md`](benchmarks/README.md). **Roadmap, measured rows, LME miss lists, external comparisons:** [`docs/memory/benchmarks/README.md`](docs/memory/benchmarks/README.md) (“memory” here means long-context retrieval evaluation, not `raw/memory/` session notes). Static hub: [`docs/memory/index.html`](docs/memory/index.html#hub-title) (if you publish GitHub Pages from `/docs`).

## Plugin development / testing

From a clone of this repo:

1. **`pip install -r requirements-dev.txt`** (pytest).
2. **`llm-wiki smoke-test`** — same as pytest against the repo root (sets `PYTHONPATH` for you).
3. Alternatively, **`PYTHONPATH=scripts python3 -m pytest tests/`** — contract tests for commands/skills, every subcommand **`--help`**, ingest registry parity, and a temp-vault ingest → build → graph flow.
4. **`llm-wiki check`** — quick vault `config.json` read + next-step hints; **`--plugin-repo`** adds `compileall` on `scripts/`.
5. Optional: **`llm-wiki check --claude-validate`** if the **`claude`** CLI is installed.
6. Optional integration: **`llm-wiki smoke-test --network`** (HTTPS reachability) and **`llm-wiki smoke-test --claude`** (`claude plugin validate`). Same via env: **`RUN_NETWORK_TESTS=1`**, **`RUN_CLAUDE_TESTS=1`** with pytest.
7. **Executable report (no LLM):** **`llm-wiki test-report`** prints a table of subprocess checks (CLI `--help`, temp vault flow, safe `llm-wiki` lines from **`commands/*.md`**, skill frontmatter). **`--json FILE`** for CI artifacts. Not a substitute for trying slash commands in Claude Code.

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for guidance on PR scope and splitting large changes.

Slash commands and skills document a per-surface **`## Smoke check`** (CLI + agent prompt) for manual runs in Claude Code.

## Green path (first-time vault)

1. **Install the plugin** (development): `claude --plugin-dir /path/to/wiki-llm` then `/reload-plugins`.
2. **Scaffold:** `llm-wiki setup --root .` → creates `llm-wiki/` with `config.json`, `wiki/`, `raw/`, `outputs/`, `CLAUDE.md`, `research-tasks.json`.
3. **Configure (optional):** `llm-wiki --vault ./llm-wiki configure -i` or set `persona.name`, `viewer`, `git`, etc.
4. **Validate:** `llm-wiki --vault ./llm-wiki validate` and, when the wiki has links, `validate --wikilinks`.
5. **Ingest:** `llm-wiki ingest <adapter> …` (see `llm-wiki ingest --list`) → material lands in `raw/`.
6. **Prepare raw (optional):** For HTML/PDF/OCR captures, use **wiki-raw-prepare** (LLM cleanup in the editor/chat), then **`llm-wiki raw finish <path> -m "what changed"`** to autofix + validate + append **`raw/.preparation-log.jsonl`** + **`[prepare]`** git commit (or run **`raw validate` / `raw record` / `git snapshot --phase prepare`** separately).
7. **Merge into wiki:** In Claude, use **wiki-ingest** / **wiki-maintainer** (or `/llm-wiki:ingest`) so topics, `wiki/index.md`, and `wiki/log.md` stay coherent.
8. **Publish viewer:** `llm-wiki build-site` → `llm-wiki/wiki/.og/`. Serve over HTTP: `cd llm-wiki/wiki/.og && python3 -m http.server` (port from `viewer.port` in config, default `8765`). URL: `http://127.0.0.1:<viewer.port>/`.
9. **Optional graphs:** `llm-wiki graph` or `graph-knowledge` → `.tmp/llm-wiki-graph/`, then `python3 -m http.server` from that folder.
10. **Optional vault git:** Enable `git.enabled`, then `llm-wiki git snapshot -m "…"` after meaningful changes. Use **phase-tagged messages** so history is auditable:
   - `git.lifecycle.phases` in config maps phases (`ingest`, `prepare`, `wiki`, `build`, …) to prefixes like `[ingest]`, `[prepare]`, `[wiki]` (defaults ship with the template).
   - `llm-wiki git snapshot -m "merged topics" --phase wiki` → subject becomes `[wiki] merged topics`.
   - `llm-wiki git lifecycle` lists recent commits with a **phase** column; `--phase ingest` filters; `--json` for tooling. Ingest snapshots already use `snapshot_message_prefix` (aligned with `phases.ingest`).
   - Optional: `snapshot_after_build` auto-commit after `build-site` (tracks `wiki/.og/` under `wiki/`). For graph bundles in `.tmp/`, tag manually: `git snapshot -m "exported graph" --phase graph` if you want it in the lifecycle audit.

## Topic research (ad-hoc)

1. In Claude, run **`/llm-wiki:research`** with a topic in the slash arguments (or describe the topic in the same turn). Follow **wiki-research**: scope → plan sources → **`llm-wiki ingest`** into **`raw/`** → optional **wiki-raw-prepare** → **wiki-ingest** / **wiki-maintainer** → append **`wiki/log.md`**.
2. This is **not** the same as **`/llm-wiki:research-loop`** (batch tasks from **`research-tasks.json`**).

## Research loop (batch)

1. Set `research_loop.enabled: true` and edit `research-tasks.json` so at least one task has `run: true`.
2. `llm-wiki research-loop --dry-run` then `llm-wiki research-loop` (YAML task files need `pip install pyyaml`). Optional: `hooks.sound` in `config.json` can run a short command (e.g. `afplay` on macOS) when a loop finishes successfully.
3. Merge new `raw/` files with **wiki-ingest** as in step 7 above (after optional raw prepare).

## Troubleshooting (green path)

| Symptom | Try |
|--------|-----|
| Plugin commands not visible | `/reload-plugins`; confirm `claude --plugin-dir` points at this repo. |
| `validate` fails (missing files) | Run `llm-wiki setup` or restore `llm-wiki/wiki/index.md`, `CLAUDE.md`, `config.json` from [`templates/llm-wiki/`](templates/llm-wiki/). |
| No **`outputs/`** (vault scaffolded before it existed) | `mkdir -p llm-wiki/outputs` and merge the **`outputs/`** section from [`templates/llm-wiki/CLAUDE.md`](templates/llm-wiki/CLAUDE.md) into your vault `CLAUDE.md`. |
| `validate --wikilinks` fails | Broken `[[links]]` to missing pages — create the target `.md` or remove the link. |
| Viewer blank / no graph | Run `build-site`; serve `wiki/.og/` with `python3 -m http.server` (not `file://`). |
| On-demand graph empty | No `wiki/**/*.md` yet, or no valid edges — add pages and wikilinks. |
| `ingest` says adapter disabled | `integrations.<id>.enabled` in config, or use `ingest --force`. |
| `research-loop` can’t read tasks | Default is JSON; for `.yaml` tasks install PyYAML. |
| Vault git refuses commands | Set `git.enabled: true` in `llm-wiki/config.json`. |
| `raw validate` fails (unbalanced fences, etc.) | Fix markdown in `raw/` or use **`--autofix`**; use **wiki-raw-prepare** for LLM cleanup; log with **`raw record`**. |
| No **`[prepare]`** in `git lifecycle` | Add `"prepare": "[prepare]"` under `git.lifecycle.phases` in `config.json` (see template). |
| Commits all show `unlabeled` in `git lifecycle` | Use prefixes from `git.lifecycle.phases` in commit subjects, or `snapshot --phase <id>`. |

## Batch PDFs → prepare → bigger graph

**`raw/` is the ingestion folder** (see [`ETHOS.md`](ETHOS.md) “Layers”). There is no second “inbox” path and no daemon watching a directory—you either copy into `raw/` or run **`llm-wiki ingest …`**, which writes there. The helper script below is **optional** (same as a `for` loop over PDFs).

1. **Dependencies:** `pip install -r requirements-optional.txt` (and **Tesseract** for scans). Use a venv if system Python is PEP 668–locked.
2. **Ingest every file under a folder** (outputs land under `raw/<out-prefix>/…/*.md`):

   ```bash
   python3 scripts/.tmp/batch_ingest_pdfs.py --vault ./llm-wiki --pdf-dir ./.tmp/PDFS --force
   ```

   (`--dry-run`, `--limit N` for testing.) Each PDF may take a long time if OCR runs on many pages. **Or** run `llm-wiki ingest pdf …` yourself per file.
3. **Prepare:** `llm-wiki raw validate … --autofix` / **`raw finish`** / **wiki-raw-prepare** (LLM) per file or in batches — see **`skills/wiki-raw-prepare/SKILL.md`**.
4. **Merge into `wiki/`** with **wiki-ingest** (and cross-link topics with **`[[wikilinks]]`**). The **link graph** (`llm-wiki graph`) is built from **`wiki/`** only — more pages + more wikilinks ⇒ bigger graph. `raw/` alone does not add graph nodes.
5. **`llm-wiki research-loop`** is **not** a PDF-folder batch; it runs tasks from **`research_loop.tasks_file`** (URLs, HN, etc.). Enable **`research_loop.enabled`** for that path.

## Automated demo (reset + full CLI)

**Local-only helpers** live under **`scripts/.tmp/`** (listed in **`.gitignore`**—not part of the published plugin). Copy or recreate them from your own snippets if you clone fresh.

From the plugin repo, **`scripts/.tmp/demo_full_flow.py`** resets **`wiki/`** from the template, clears **`raw/`**, ingests **`README.md`** into **`raw/notes/demo-readme.md`**, runs **`raw validate` / `raw finish`**, writes a stub **`wiki/demo.md`** (stand-in for **wiki-ingest** in chat), then **`build-site`**, **`validate --wikilinks`**, and **`graph`**. Default vault: **`.tmp/vault-smoke/llm-wiki`**; override with **`--vault`**.

```bash
python3 scripts/.tmp/demo_full_flow.py
```

## Related

- Slash commands: [`commands/`](commands/)
- CLI reference: [README.md#cli-binllm-wiki](README.md)
- Optional pairing with [gstack](https://github.com/garrytan/gstack) for browser QA / ship workflows: [README.md#using-llm-wiki-with-gstack](README.md#using-llm-wiki-with-gstack)
