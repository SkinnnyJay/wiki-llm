<p align="center">
  <img src="assets/readme-banner.png" alt="llm-wiki" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/SkinnnyJay/wiki-llm" title="Repository on GitHub"><img src="https://img.shields.io/badge/GitHub-repo-181717?logo=github&logoColor=white" alt="GitHub repo"/></a>
  &nbsp;
  <a href="https://github.com/SkinnnyJay/wiki-llm#install-claude-code" title="Install the plugin in Claude Code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-D4A574?logo=anthropic&logoColor=white" alt="Claude Code plugin"/></a>
  &nbsp;
  <a href="https://github.com/SkinnnyJay/wiki-llm/blob/main/AGENTS.md" title="AGENTS.md for Cursor and Codex"><img src="https://img.shields.io/badge/Cursor-rules%20%2B%20plugin-000000?logo=cursor&logoColor=white" alt="Cursor rules"/></a>
</p>


# QA Playbook — wiki-llm

> **Maintainer QA only — not user onboarding.** Use [`QUICKSTART.md`](./QUICKSTART.md) for first-time setup and [`WORKFLOWS.md`](../WORKFLOWS.md) for normal vault use.

Manual test suite for verifying the full plugin flow before releases.
Run through each section after significant changes; mark pass/fail in your notes.

> **Quick smoke:** `bin/llm-wiki smoke-test -v` runs the full pytest suite (contracts, CLI help, vault flow, E2E, hooks, MCP stdio, golden replay). Opt-in tiers: **`--network`**, **`--claude`**, **`--browser`** (sets `RUN_*` env vars; pytest prints one-time **stderr banners** when those tiers are on). See **§25** (pytest tiers), **§26** (playbook vs tests), **§27** (automation levels — what can and cannot be asserted in CI).
> This playbook also covers **manual** steps (full viewer UX, marketplace install, cross-tool parity) beyond the automated viewer smoke.

---

## Prerequisites

| Requirement | How to verify |
|-------------|---------------|
| Python 3.10+ | `python3 --version` |
| Repo cloned | `ls bin/llm-wiki` |
| No stale vault | `rm -rf llm-wiki/` (fresh scaffold each run) |
| Optional: ChromaDB | `pip install chromadb` (for hybrid/chromadb tests) |
| Optional: `rg` (ripgrep) | `rg --version` (grep backend) |
| `.env` populated | Copy `.env.example` → `.env`, fill API keys you intend to test |

---

## 0 — Automated gate (run first)

| # | Test | Command | Pass criteria |
|---|------|---------|---------------|
| 0.1 | Unit + contract tests | `bin/llm-wiki smoke-test -v` | Exit 0, no failures |
| 0.2 | Agent doc sync check | `bin/llm-wiki sync-agent-docs --check` | Exit 0 |
| 0.3 | Plugin-repo check | `bin/llm-wiki check --plugin-repo` | Exit 0 |
| 0.4 | Compile check | `python3 -m compileall scripts/ -q` | Exit 0 |

---

## 1 — Setup flow

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 1.1 | Fresh setup (defaults) | `bin/llm-wiki setup --defaults` | Prints `Scaffolded vault at …/llm-wiki`; `llm-wiki/config.json`, `wiki/index.md`, `CLAUDE.md` exist |
| 1.2 | Interactive setup | `bin/llm-wiki setup -i` | Wizard prompts for persona, git, viewer, MCP, search backend, KG, memory, research loop; answers are saved in `config.json` |
| 1.3 | Setup with custom vault | `bin/llm-wiki setup --vault /tmp/test-vault` | Vault created at `/tmp/test-vault`; clean up after |
| 1.4 | Re-run setup (idempotent) | Run `setup --defaults` twice | No crash; `dirs_exist_ok` works; existing config preserved or merged |
| 1.5 | Git init on setup | Set `git.init_on_setup: true` in config before setup, or answer yes in wizard | `llm-wiki/.git` exists; `Initialized git repository` printed |
| 1.6 | Validate after setup | `bin/llm-wiki validate` | `OK` — config.json, wiki/index.md, CLAUDE.md all present |

---

## 2 — Configuration

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 2.1 | CLI configure (non-interactive) | `bin/llm-wiki configure --persona-name "TestBot"` | `config.json` → `persona.name` is `"TestBot"` |
| 2.2 | CLI configure (interactive) | `bin/llm-wiki configure -i` | Wizard prompts; changes written |
| 2.3 | Invalid config.json | Corrupt `config.json` (e.g., trailing comma) → `bin/llm-wiki validate` | Exit 1, `Invalid config.json` message |
| 2.4 | Env var vault override | `LLM_WIKI_VAULT=./llm-wiki bin/llm-wiki validate` | Resolves vault via env |

---

## 3 — Ingest flow

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 3.1 | List adapters | `bin/llm-wiki ingest --list` | Prints all adapter IDs and labels; exit 0 |
| 3.2 | Ingest a local file | Create `llm-wiki/raw/clips/test-note.md` with valid frontmatter → `bin/llm-wiki ingest file llm-wiki/raw/clips/test-note.md` | Prints ingest result; file appears under `raw/`; dedup hash registered |
| 3.3 | Dedup blocks duplicate | Ingest the same file again without `--force` | Exit 2 or dedup message; file not re-ingested |
| 3.4 | Force re-ingest | `bin/llm-wiki ingest file … --force` | Succeeds despite duplicate |
| 3.5 | Security scan | Ingest a file containing `<script>alert(1)</script>` or prompt injection markers | `SECURITY: prompt_injection suspected` printed; exit 2 if `block_on_suspected` |
| 3.6 | Force security bypass | `bin/llm-wiki ingest file … --force-security` | Ingests despite security warning |
| 3.7 | Tagging | Ingest a file with `--tags "topic1,topic2"` | Frontmatter contains `llm_wiki_tags: [topic1, topic2]` |
| 3.8 | KG auto-update on ingest | Set `knowledge_graph.auto_update_on_ingest: true` → ingest | `KG: auto-update` message printed |
| 3.9 | Git snapshot on ingest | Set `git.enabled: true` with `.git` init'd → ingest | Git log shows `[ingest] …` commit |
| 3.10 | No adapter args | `bin/llm-wiki ingest` (no adapter) | Exit 1 with usage message |

---

## 4 — Raw prepare flow

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 4.1 | Raw validate (valid file) | `bin/llm-wiki raw validate llm-wiki/raw/clips/test-note.md` | `OK` printed |
| 4.2 | Raw validate (broken file) | Create a raw file with no frontmatter or broken structure → validate | Exit 1 with structural issues on stderr |
| 4.3 | Raw validate with autofix | `bin/llm-wiki raw validate <file> --autofix` | `Autofix:` lines printed; file corrected |
| 4.4 | Raw validate session memory (skip) | `bin/llm-wiki raw validate llm-wiki/raw/memory/test.md` | `OK (skipped — session memory)` |
| 4.5 | Raw record | `bin/llm-wiki raw record llm-wiki/raw/clips/test-note.md --goal "test"` | `Logged → raw/.preparation-log.jsonl` |
| 4.6 | Raw finish | `bin/llm-wiki raw finish llm-wiki/raw/clips/test-note.md -m "test prepare"` | Autofix + validate + log + git `[prepare]` commit (if git enabled) |
| 4.7 | Raw finish skip-git | `bin/llm-wiki raw finish … --skip-git` | No git commit; message about manual snapshot |
| 4.8 | Raw rebuild-index | `bin/llm-wiki raw rebuild-index` | Index rebuilt; exit 0 |

---

## 5 — Validate & lint

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 5.1 | Full validate | `bin/llm-wiki validate` | `OK` with all required files present |
| 5.2 | Validate with wikilinks | `bin/llm-wiki validate --wikilinks` | Reports broken `[[wikilinks]]` if any exist |
| 5.3 | Missing required file | Delete `llm-wiki/wiki/index.md` → validate | Exit 1 with `missing wiki/index.md` |
| 5.4 | List topics | `bin/llm-wiki list-topics` | Lists all wiki topic files |

---

## 6 — Search backends

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 6.1 | FTS5 search (default) | Set `mcp.search_backend: "fts5"` → use MCP `wiki_search` or CLI equivalent | Results returned; BM25-ranked |
| 6.2 | FTS5 reindex | `bin/llm-wiki mcp` → call `wiki_reindex` tool | Index rebuilt; subsequent searches include new content |
| 6.3 | FTS5 bad query | Search with special chars (`AND OR NOT "`) | No crash; empty or sanitized results |
| 6.4 | Grep backend | Set `mcp.search_backend: "grep"` | Search works (slower; no persistent index) |
| 6.5 | Grep with rg available | Ensure `rg` is on PATH | Uses ripgrep path |
| 6.6 | Grep without rg | Temporarily hide `rg` from PATH | Falls back to regex walk; still returns results |
| 6.7 | ChromaDB backend | Set `mcp.search_backend: "chromadb"` (requires pip install) | Semantic search returns results |
| 6.8 | ChromaDB fallback | Set `mcp.search_backend: "chromadb"` **without** chromadb installed | Warning printed; falls back to grep |
| 6.9 | Hybrid backend | Set `mcp.search_backend: "hybrid"` (requires chromadb) | RRF fusion of FTS5 + Chroma results |
| 6.10 | Hybrid fallback | Set `mcp.search_backend: "hybrid"` without chromadb | Warning; falls back to fts5 |
| 6.11 | Search index status | MCP tool `wiki_search_index_status` | Reports backend type, doc count, staleness |

---

## 7 — Knowledge graph

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 7.1 | KG add | `bin/llm-wiki kg add "Python" "is-a" "Language" --source wiki/topics/python.md` | Triple ID printed |
| 7.2 | KG query | `bin/llm-wiki kg query "Python"` | Lists triples involving "Python" |
| 7.3 | KG invalidate | `bin/llm-wiki kg invalidate "Python" "is-a" "Language"` | Match printed; triple marked ended |
| 7.4 | KG invalidate (no match) | `bin/llm-wiki kg invalidate "NoEntity" "x" "y"` | Exit 1, `No matching triple` |
| 7.5 | KG timeline | `bin/llm-wiki kg timeline` | Chronological triple list |
| 7.6 | KG timeline (entity) | `bin/llm-wiki kg timeline "Python"` | Filtered timeline |
| 7.7 | KG stats | `bin/llm-wiki kg stats` | Triple count, entity count, etc. |
| 7.8 | KG rebuild | `bin/llm-wiki kg rebuild` | `Rebuilt: N triples added …` |
| 7.9 | JSON backend (default) | `knowledge_graph.backend: "json"` → kg add/query | Uses `.kg.json` |
| 7.10 | SQLite backend | `knowledge_graph.backend: "sqlite"` → kg add/query | Uses `.kg.sqlite3` |
| 7.11 | SQLite fallback | Set `sqlite` but break import → kg add | Falls back to JSON backend |

---

## 8 — Session memory

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 8.1 | Memory disabled (graceful) | Set `memory.enabled: false` → `bin/llm-wiki memory save -s test --summary "hi"` | Prints skip message; exit 0 (not failure) |
| 8.2 | Memory save | Enable memory → `bin/llm-wiki memory save -s my-session --summary "test session" --tags "tag1"` | File created under `raw/memory/` |
| 8.3 | Memory log | `bin/llm-wiki memory log -s my-session` | Prints log entries |
| 8.4 | Memory list | `bin/llm-wiki memory list` | Lists sessions; `--json` outputs JSON |
| 8.5 | Memory list by tag | `bin/llm-wiki memory list --tag tag1` | Filtered results |
| 8.6 | Memory show | `bin/llm-wiki memory show my-session` | Session contents displayed |
| 8.7 | Memory show --current | Write `.current-session` → `bin/llm-wiki memory show -c` | Resolves current session ID |
| 8.8 | Memory recall | `bin/llm-wiki memory recall "test" --limit 5` | Matching entries returned |
| 8.9 | Memory recall scoped | `bin/llm-wiki memory recall "test" -c` | Only current session searched |
| 8.10 | Memory prune (dry-run) | `bin/llm-wiki memory prune --dry-run --older-than 0` | Shows what would be pruned; nothing deleted |
| 8.11 | Memory prune | `bin/llm-wiki memory prune --older-than 0` | Old sessions removed |
| 8.12 | Bad metadata JSON | `bin/llm-wiki memory save -s x --metadata "{bad"` | Exit 1 |
| 8.13 | No session ID | `bin/llm-wiki memory save` (no `-s` or `-c`) | Error or usage message |

---

## 9 — Git integration

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 9.1 | Git init | `bin/llm-wiki git init` (with `git.enabled: true`) | `.git` created; success message |
| 9.2 | Git disabled | Set `git.enabled: false` → `bin/llm-wiki git status` | Exit 1, `GitDisabledError` message |
| 9.3 | Git status | `bin/llm-wiki git status` | Shows working tree status |
| 9.4 | Git log | `bin/llm-wiki git log -n 5` | Recent commits listed |
| 9.5 | Git log with grep | `bin/llm-wiki git log --grep "ingest"` | Filtered commits |
| 9.6 | Git diff | `bin/llm-wiki git diff` | Shows uncommitted changes |
| 9.7 | Git diff staged | `bin/llm-wiki git diff --staged` | Shows staged changes |
| 9.8 | Git snapshot | `bin/llm-wiki git snapshot -m "test snapshot"` | Commit created with message |
| 9.9 | Git snapshot with phase | `bin/llm-wiki git snapshot -m "msg" --phase ingest` | Commit with `[ingest]` prefix |
| 9.10 | Git snapshot bad phase | `bin/llm-wiki git snapshot -m "msg" --phase bogus` | Exit 1 if phase not in `lifecycle.phases` |
| 9.11 | Git snapshot no message | `bin/llm-wiki git snapshot` (no `-m`) | Exit 1, `--message required` |
| 9.12 | Git lifecycle | `bin/llm-wiki git lifecycle --json` | JSON output of lifecycle phases |
| 9.13 | Git query | `bin/llm-wiki git query "search term"` | Searches git log/content |

---

## 10 — MCP server

### 10a — Stdio transport

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 10.1 | Start stdio MCP | `echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' \| bin/llm-wiki mcp` | Returns JSON-RPC response listing tools |
| 10.2 | MCP disabled | Set `mcp.enabled: false` → `bin/llm-wiki mcp` | Exit 1, `MCP server disabled` |
| 10.3 | wiki_status tool | Send JSON-RPC `wiki_status` call | Returns vault status info |
| 10.4 | wiki_search tool | Send `wiki_search` with query | Returns search results |
| 10.5 | wiki_ingest tool | Send `wiki_ingest` with adapter + source | Adapter runs + `post_ingest`; returns message and exit info |
| 10.6 | wiki_validate tool | Send `wiki_validate` | Returns validation status |
| 10.7 | wiki_kg_query tool | Send `wiki_kg_query` with entity | Returns KG triples |
| 10.8 | memory_save tool | Send `memory_save` | Saves session memory |
| 10.9 | memory_recall tool | Send `memory_recall` with query | Returns matching memories |
| 10.10 | wiki_benchmark_run | Send `wiki_benchmark_run` with suite | Runs benchmark; returns metrics |
| 10.18 | tools_mode read_only | Set `mcp.tools_mode: read_only` → `tools/list` | No mutating tools (`wiki_kg_add`, `wiki_configure`, …) |
| 10.19 | benchmark_tool_enabled | Set `mcp.benchmark_tool_enabled: false` → `tools/list` | `wiki_benchmark_run` and `wiki_benchmark_suites` absent |
| 10.20 | configure_allowlist | Set `mcp.configure_allowlist` to e.g. `["viewer."]` → `wiki_configure` for `mcp.*` | Result `success: false`, allowlist error |
| 10.21 | Invalid `wiki_search` scope | `tools/call` with `scope: "bad"` | JSON-RPC error `-32602` |
| 10.22 | max_response_chars | Set `mcp.max_response_chars: 80` → `wiki_status` | Truncation marker in text payload |

### 10b — SSE/HTTP transport

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 10.11 | Start SSE server | `bin/llm-wiki mcp --transport sse --port 8891` | Server listening on 127.0.0.1:8891 |
| 10.12 | HTTP POST / | `curl -X POST http://127.0.0.1:8891/ -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'` | JSON-RPC tools list response |
| 10.13 | HTTP POST /mcp | Same as above but to `/mcp` | Same response |
| 10.14 | Invalid JSON body | POST garbage body | HTTP 400 |
| 10.15 | Port already in use | Start SSE on occupied port | Error message, exit 1 |
| 10.23 | sse_require_loopback | `mcp.sse_require_loopback: true`, host `0.0.0.0` | Process exits 1; stderr mentions loopback |
| 10.24 | sse_token | Set `mcp.sse_token` → POST without `Authorization` / `X-LLM-Wiki-Token` | HTTP 401 |
| 10.25 | JSON-RPC notification | POST `{"jsonrpc":"2.0","method":"notifications/initialized"}` (no `id`) | HTTP **204**; empty body |
| 10.26 | Stdio notification | Same `notifications/initialized` line to stdio MCP | Exit 0; **no stdout** line |
| 10.27 | Size limits | Documented in [`skills/references/mcp-and-kg.md`](../skills/references/mcp-and-kg.md) § Limits | stdio line ≤ 32 MiB; HTTP `Content-Length` ≤ 32 MiB; tool JSON capped by `mcp.max_response_chars` |

### 10c — MCP install

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 10.16 | MCP install | `bin/llm-wiki mcp install` | Writes `~/.claude/claude_desktop_config.json` entry and `./mcp.json` |
| 10.17 | MCP start (background) | `bin/llm-wiki mcp start --port 8891` | Background process; lock file; log at `.mcp-sse.log` |

---

## 11 — Static site viewer

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 11.1 | Build site | `bin/llm-wiki build-site` | `Built site → wiki/.og`; `wiki-data.json` and HTML assets exist |
| 11.2 | Build site (viewer disabled) | Set `viewer.enabled: false` → `bin/llm-wiki build-site` | Prints skip message; returns `.og` path |
| 11.3 | Build site if-stale | `bin/llm-wiki build-site --if-stale` (no changes) | `Site is up-to-date; skipping build.` |
| 11.4 | Serve viewer | `scripts/serve-viewer.sh --vault llm-wiki` → open browser at `http://127.0.0.1:8765/` | Page loads; file tree visible; D3 graph renders |
| 11.5 | Client-side search | Type in search box (Cmd/Ctrl+K) | Filters file tree by title/path |
| 11.6 | Markdown reader | Click a wiki page | Markdown rendered; frontmatter stripped; links work |
| 11.7 | D3 force graph | Click graph tab/view | Nodes and edges render; drag, zoom, click-to-select work |
| 11.8 | Open in editor | Set `viewer.open_file_scheme: "cursor"` → click "Open in …" | Opens `cursor://file/…` link |
| 11.9 | Sidebar collapse | Click sidebar collapse button | Sidebar toggles; content area expands |

---

## 12 — Graph generation

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 12.1 | Link graph | `bin/llm-wiki graph` | `Graph bundle → …`; HTML + JSON generated |
| 12.2 | Knowledge graph mode | `bin/llm-wiki graph --mode knowledge` | Knowledge graph data in output |
| 12.3 | Graph-knowledge alias | `bin/llm-wiki graph-knowledge` | Same as `graph --mode knowledge` |
| 12.4 | Custom output dir | `bin/llm-wiki graph --out /tmp/test-graph` | Bundle at specified path |
| 12.5 | Empty wiki | Remove all wiki files → `bin/llm-wiki graph` | Minimal/empty graph; no crash |
| 12.6 | Serve graph | `scripts/serve-graph.sh --vault llm-wiki` → open browser at `http://127.0.0.1:8890/` | Interactive graph renders |

---

## 13 — Research loop

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 13.1 | Research loop disabled | Set `research_loop.enabled: false` → `bin/llm-wiki research-loop` | Exit 1 |
| 13.2 | Dry run | `bin/llm-wiki research-loop --dry-run` | Lists tasks without executing |
| 13.3 | Run single task | `bin/llm-wiki research-loop --task <id>` | Only that task runs |
| 13.4 | Full loop | Enable research loop + populate `research-tasks.json` with valid tasks → `bin/llm-wiki research-loop` | Tasks executed; raw files created |
| 13.5 | Force re-run | `bin/llm-wiki research-loop --force` | Reruns even previously completed tasks |
| 13.6 | Missing tasks file | Delete `research-tasks.json` → run | Error message; exit 1 |

---

## 14 — Benchmarks

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 14.1 | List suites | `bin/llm-wiki benchmark suites` | Prints LME, LoCoMo, ConvoMem with descriptions |
| 14.2 | Benchmark disabled | Set `benchmark.enabled: false` → `bin/llm-wiki benchmark run lme` | Exit 1 |
| 14.3 | Run LME | `bin/llm-wiki benchmark run lme --backend fts5 --limit 5` | Metrics printed; results recorded |
| 14.4 | Run LME all backends | `bin/llm-wiki benchmark run lme --backend all --limit 5` | Runs across fts5, grep, (chromadb, hybrid if available) |
| 14.5 | Run LoCoMo | `bin/llm-wiki benchmark run locomo --data <path> --limit 5` | Metrics printed |
| 14.6 | Run ConvoMem | `bin/llm-wiki benchmark run convomem --data <path> --limit 5` | Metrics printed |
| 14.7 | Benchmark report | `bin/llm-wiki benchmark report` | Formatted report of past runs |
| 14.8 | Benchmark history | `bin/llm-wiki benchmark history --limit 5` | Recent run entries |
| 14.9 | Benchmark compare | `bin/llm-wiki benchmark compare --a <snap1> --b <snap2>` | Side-by-side comparison |
| 14.10 | Benchmark analyze | `bin/llm-wiki benchmark analyze --suite lme --failures` | Failure analysis |
| 14.11 | Unknown suite | `bin/llm-wiki benchmark run nosuchsuite` | Error message; exit 1 |

---

## 15 — Metrics

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 15.1 | Metrics record | `bin/llm-wiki metrics record` | Records metrics snapshot |
| 15.2 | Metrics query | `bin/llm-wiki metrics query --key <key>` | Returns matching metrics |
| 15.3 | Metrics stats | `bin/llm-wiki metrics stats` | Summary statistics |
| 15.4 | Metrics report | `bin/llm-wiki metrics report` | Formatted report |
| 15.5 | Metrics summary | `bin/llm-wiki metrics summary` | High-level summary |
| 15.6 | Metrics clear | `bin/llm-wiki metrics clear --yes` | Clears metrics DB |

---

## 16 — Agent doc sync

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 16.1 | Sync (generate) | Edit `docs/AGENTS.shared.md` → `bin/llm-wiki sync-agent-docs` | `AGENTS.md`, `CLAUDE.md`, `rules/llm-wiki.mdc` updated |
| 16.2 | Sync check (pass) | After sync → `bin/llm-wiki sync-agent-docs --check` | Exit 0 |
| 16.3 | Sync check (fail) | Manually edit `AGENTS.md` to diverge → `--check` | Non-zero exit; reports mismatch |
| 16.4 | Missing shared doc | Remove `docs/AGENTS.shared.md` → sync | Error message |

---

## 17 — Plugin / integrations

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 17.1 | Integrations status | `bin/llm-wiki integrations status` | Lists adapters and their enabled/configured state |
| 17.2 | Integrations validate | `bin/llm-wiki integrations validate` | Checks API keys / connectivity |
| 17.3 | Set integration key | `bin/llm-wiki integrations set-key firecrawl <key>` | Key saved to config |
| 17.4 | Integrations wizard | `bin/llm-wiki integrations wizard` | Interactive adapter configuration |
| 17.5 | Deps check | `bin/llm-wiki deps check` | Reports optional dependency status |
| 17.6 | Claude plugin manifest | Check `.claude-plugin/plugin.json` | Valid JSON; `mcpServers`, `userConfig`, `commands` present |
| 17.7 | Cursor plugin manifest | Check `.cursor-plugin/plugin.json` | Valid JSON; Cursor marketplace fields present |

---

## 18 — Error paths & edge cases

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 18.1 | No vault exists | `rm -rf llm-wiki/ && bin/llm-wiki validate` | Graceful error (missing config/files), not a traceback |
| 18.2 | Empty wiki directory | Setup → remove all wiki files → `bin/llm-wiki validate` | Reports missing `wiki/index.md` |
| 18.3 | Broken wikilinks | Add `[[nonexistent-page]]` in a wiki file → `validate --wikilinks` | Reports broken link |
| 18.4 | Corrupt config.json | Write invalid JSON → any command | `Invalid config.json` error; exit 1 |
| 18.5 | Permission denied | `chmod 000 llm-wiki/config.json` → validate | I/O error message; not a raw traceback |
| 18.6 | Concurrent access | Run two `ingest` commands simultaneously | No data corruption; at worst one fails gracefully |
| 18.7 | Unicode in paths/content | Create a raw file with unicode filename/content → ingest + search | Handles correctly; no encoding errors |
| 18.8 | Very large file | Ingest a 10MB+ markdown file | Completes (may be slow); no OOM |
| 18.9 | Empty search query | Search with empty string | Empty results or usage hint; no crash |
| 18.10 | FTS5 special characters | Search with `"quotes" AND OR NOT ( )` | Sanitized query; no `OperationalError` |

---

## 19 — CLI help & discoverability

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 19.1 | Top-level help | `bin/llm-wiki --help` | Lists all subcommands; exit 0 |
| 19.2 | Each subcommand help | `bin/llm-wiki <subcommand> --help` for every subcommand | Exit 0; coherent help text |
| 19.3 | Unknown subcommand | `bin/llm-wiki nosuchcommand` | Error with suggestion or usage; not a traceback |
| 19.4 | Wake-up | `bin/llm-wiki wake-up` | Prints vault status summary |
| 19.5 | Check (vault) | `bin/llm-wiki check` | Runs vault health checks |

---

## 20 — Hooks (Claude Code / Cursor)

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 20.1 | PreCompact hook | Trigger Claude Code compact (or simulate) | `llm_wiki_precompact.sh` runs without error |
| 20.2 | Stop hook | End a Claude Code session (or simulate) | `llm_wiki_stop.sh` runs |
| 20.3 | Memory hook | End session with `memory.enabled: true` | `llm_wiki_memory.sh` saves session memory |
| 20.4 | Sound hook | Set `hooks.sound.enabled: true` with `on_ingest: true` → ingest | Sound command fires (or logs attempt) |
| 20.5 | Hook scripts exist | `ls hooks/` | `hooks.json`, shell scripts present and executable |

---

## 21 — Slash commands (Claude Code / Cursor)

Verify each command file exists and contains coherent prompt text.

| # | Command | File | Quick check |
|---|---------|------|-------------|
| 21.1 | setup | `commands/setup.md` | Slash `/llm-wiki:setup` (also `/llm-wiki:wiki-setup`); wizard in `skills/wiki-setup/SKILL.md` |
| 21.2 | ingest | `commands/ingest.md` | References adapter flow |
| 21.3 | query | `commands/query.md` | References search + citations |
| 21.4 | research | `commands/research.md` | References research skill |
| 21.5 | research-loop | `commands/research-loop.md` | References batch tasks |
| 21.6 | raw-prepare | `commands/raw-prepare.md` | References validate/finish |
| 21.7 | lint | `commands/lint.md` | References wiki-lint skill |
| 21.8 | memory | `commands/memory.md` | References session memory |
| 21.9 | benchmark | `commands/benchmark.md` | References benchmark suite |
| 21.10 | mcp | `commands/mcp.md` | References MCP server |
| 21.11 | graph / graph-knowledge | `commands/graph.md`, `commands/graph-knowledge.md` | Reference graph generation |
| 21.12 | git-* | `commands/git-*.md` | Reference git subcommands |
| 21.13 | build-og | `commands/build-og.md` | References build-site |
| 21.14 | integrations | `commands/integrations.md` | References adapter config |

---

## 22 — Skills (spot-check in Claude Code / Cursor)

These tests require an agent environment (Claude Code, Cursor, or Codex).

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 22.1 | wiki-setup | Ask agent to set up a vault | Agent follows `skills/wiki-setup/SKILL.md`; vault scaffolded |
| 22.2 | wiki-query | Ask "What do we know about X?" | Agent searches wiki, cites sources |
| 22.3 | wiki-ingest | Ask agent to ingest a URL | Agent uses fetch/adapter → raw → wiki merge |
| 22.4 | wiki-raw-prepare | Ask agent to prepare a raw file | Agent validates, autofixes, logs, commits |
| 22.5 | wiki-pipeline | Ask for end-to-end pipeline | Agent runs full flow with gates |
| 22.6 | wiki-status | Ask for vault health | Agent reports status dashboard |
| 22.7 | wiki-research | Ask to research a topic | Agent orchestrates fetch → ingest → wiki |
| 22.8 | wiki-session-memory | Ask agent to save/recall memory | Agent uses memory commands |
| 22.9 | wiki-lint | Ask agent to lint the wiki | Agent reports orphans, stale claims, etc. |
| 22.10 | wiki-retro | Ask for a retrospective | Agent analyzes logs/git |
| 22.11 | wiki-learn | Ask agent to learn a preference | Agent updates `.agent-memory.md` |
| 22.12 | wiki-upgrade | Ask to upgrade plugin | Agent pulls latest, re-runs setup |

---

## 23 — End-to-end scenario

Run this full scenario to verify the entire pipeline works together.

```
# 1. Fresh setup
rm -rf llm-wiki/
bin/llm-wiki setup --defaults

# 2. Configure
bin/llm-wiki configure --persona-name "QA Bot"

# 3. Validate
bin/llm-wiki validate

# 4. Create and ingest a test file
mkdir -p llm-wiki/raw/clips
cat > llm-wiki/raw/clips/qa-test.md << 'EOF'
---
title: QA Test Note
source: manual
date: 2026-04-09
---

# QA Test Note

This is a test note for the QA playbook. It covers [[index]] linking
and search retrieval. Topics include testing, quality assurance, and
wiki pipelines.
EOF

bin/llm-wiki ingest file llm-wiki/raw/clips/qa-test.md --tags "qa,test"

# 5. Raw prepare
bin/llm-wiki raw validate llm-wiki/raw/clips/qa-test.md
bin/llm-wiki raw finish llm-wiki/raw/clips/qa-test.md -m "QA test note" --skip-git

# 6. Build site
bin/llm-wiki build-site

# 7. Validate with wikilinks
bin/llm-wiki validate --wikilinks

# 8. Knowledge graph
bin/llm-wiki kg add "QA" "related-to" "Testing" --source wiki/topics/qa.md
bin/llm-wiki kg query "QA"
bin/llm-wiki kg stats

# 9. Session memory
bin/llm-wiki memory save -s qa-session --summary "QA playbook test run" --tags "qa"
bin/llm-wiki memory list
bin/llm-wiki memory recall "qa"
bin/llm-wiki memory show qa-session

# 10. Graph
bin/llm-wiki graph

# 11. Metrics
bin/llm-wiki metrics stats

# 12. Final validate
bin/llm-wiki validate
bin/llm-wiki check

echo "=== E2E scenario complete ==="
```

**Pass criteria:** Every command exits 0 (or expected non-zero where noted); no tracebacks; files exist at expected paths.

---

## 24 — Regression checklist

After any code change, verify these do not regress:

- [ ] `bin/llm-wiki smoke-test -v` passes (includes E2E, hooks, MCP stdio, golden replay)
- [ ] `bin/llm-wiki smoke-test --replay` passes (replay-only quick check)
- [ ] `bin/llm-wiki sync-agent-docs --check` passes
- [ ] `bin/llm-wiki check --plugin-repo` passes
- [ ] `python3 -m compileall scripts/ -q` passes
- [ ] Section 23 E2E scenario completes cleanly
- [ ] MCP stdio `tools/list` returns all expected tools
- [ ] FTS5 search returns results after ingest + reindex
- [ ] Session memory save/recall round-trips
- [ ] KG add/query round-trips
- [ ] `build-site` produces valid `wiki-data.json`
- [ ] All `--help` flags exit 0

---

## 25 — Automation harness (tiers, recording, cleanup)

**Tiers**

| Tier | What | Command | Cost |
|------|------|---------|------|
| 1–2 | Contracts + CLI `--help` | `bin/llm-wiki smoke-test -v` | Free |
| 3 | Deterministic E2E (`tests/test_e2e_flow.py`) | same | Free |
| 4 | Hook scripts (`tests/test_hooks.py`, needs `jq`) | same | Free |
| 5 | MCP stdio JSON-RPC (`tests/test_mcp_contract.py`) | same | Free |
| 6 | Golden replay (`tests/test_replay_golden.py`, `tests/fixtures/golden/*.json`) | `bin/llm-wiki smoke-test -v` or `bin/llm-wiki smoke-test --replay` | Free |
| 7 | Agent skill evals (`tests/test_skill_evals.py`, `tests/skill_eval_cases.py`) | `RUN_CLAUDE_TESTS=1 bin/llm-wiki smoke-test --claude` | Agent CLI usage — **full** list is all non-excluded `wiki-*` skills in `SKILL_EVALS`; network/API extract + web research skills are listed in `SKILL_EVAL_EXCLUDE` (see `tests/test_plugin_inventory.py`) |
| 7b | Optional Codex mirror (`tests/test_skill_evals_codex.py`) | `RUN_CODEX_SKILL_EVALS=1` + `pytest …` | Same scenarios as tier 7 (honours `RUN_MINIMAL_SKILL_EVALS` like Claude) |
| 7c | Minimal skill evals (dev) | `RUN_MINIMAL_SKILL_EVALS=1` with tier 7 / `--claude` | Only wiki-query, wiki-status, wiki-session-memory |
| 8 | Viewer smoke (`tests/test_viewer_playwright.py`) | `RUN_BROWSER_TESTS=1 bin/llm-wiki smoke-test --browser` (needs `pip install playwright` + `playwright install chromium`) | Local Chromium only (not an LLM) |

Tier 7 runs **`claude -p`** against shared scenarios in **`tests/skill_eval_cases.py`**. Optional **`tests/test_skill_evals_codex.py`** runs the same cases via **`codex exec`** when **`RUN_CODEX_SKILL_EVALS=1`**. Non-zero exit fails the test (full stdout/stderr on assertion). **`SKILL_EVAL_BACKEND`** on **`skill_eval_runner`** (in `conftest`) defaults to **claude** if anything still uses that fixture.

**Golden replay**

- Committed fixtures live under `tests/fixtures/golden/*.json` (schema: `steps` with `argv`, optional `file_checks`, `purge_vault_after`).
- Run **only** replay-marked tests: `bin/llm-wiki smoke-test --replay` (equivalent to `pytest tests -m replay`).

**Record → extract (optional, one-time / when changing flows)**

1. `python3 scripts/qa_record.py --scenario <name>` (requires `claude` on PATH and credentials). Writes `tests/fixtures/recordings/*.jsonl` (gitignored).
2. `python3 scripts/qa_extract_fixture.py tests/fixtures/recordings/<file>.jsonl -o tests/fixtures/golden/<name>.json`
3. Review and edit the JSON; commit the golden file.

**Claude CLI (skill evals + recording)**

`test_skill_evals.py` uses `claude -p` with `--no-session-persistence` and `--dangerously-skip-permissions`. **`claude_runner`** uses **`_env_for_skill_eval`**, **`stdin=DEVNULL`**, **`--add-dir` `<vault>`** and **`--`** before the prompt (so the prompt is not parsed as another `--add-dir` path), and **drops `ANTHROPIC_*` from the subprocess env by default** (so pytest does not inherit API keys from `.env` / IDE). By default **`--setting-sources=project`**: **`~/.claude/settings.json`** is *not* merged (its `env` block often injects an API key and forces **API credits**, which fails with “Credit balance is too low” while **Claude Max** still works in an interactive session). Override with **`CLAUDE_RUNNER_SETTING_SOURCES=user,project,local`** to match full interactive merges. Set **`CLAUDE_RUNNER_KEEP_ANTHROPIC_ENV=1`** to pass API keys through. **`--bare` is opt-in.** `scripts/qa_record.py` supports `--bare`, `--no-max-budget`, `--keep-anthropic-env`, and the same **`CLAUDE_RUNNER_SETTING_SOURCES`** default when not `--bare`.

**Manual `claude -p` (portable paths)** — use the plugin repo root and vault as variables, not hardcoded machine paths:

```bash
# Run from the plugin repo (clone) root, or set REPO_ROOT explicitly.
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
VAULT="${LLM_WIKI_VAULT:-$REPO_ROOT/templates/llm-wiki}"
export PATH="$REPO_ROOT/bin:${PATH}"
export LLM_WIKI_VAULT="$VAULT"

# Replace the final quoted string with your real task (the line below matches tier-7 wiki-query).
claude -p --setting-sources project --no-session-persistence --dangerously-skip-permissions \
  --output-format text --plugin-dir "$REPO_ROOT" --add-dir "$VAULT" -- \
  'You are in the llm-wiki vault. Answer in 2 sentences: what do we know about authentication or OAuth? You must cite at least one path under wiki/ (e.g. wiki/auth.md).'
```

**Cleanup**

- Pytest `tmp_path` removes per-test vaults.
- E2E and golden replay tests end with `teardown --purge --yes` where applicable.
- Session finalizer in `tests/conftest.py` prunes dead `~/.claude/sessions/*.json` locks and empty `~/.claude/session-env/` dirs after the test session.

---

## 26 — Automated coverage vs playbook (matrix)

**Intent:** `smoke-test` is the default gate; it does **not** replace every manual row above. Use this table to see what pytest already exercises and what remains **manual** or **opt-in**.

| Playbook area | Automated tests (default `smoke-test`) | Gaps / manual |
|---------------|----------------------------------------|----------------|
| **§0** Gate | `sync_agent_docs.test.py` (shared doc parity); `test_check_plugin_repo_cli_matches_qa_gate` (`check --plugin-repo`); `compileall` via that check | §0.4 alone: also run `python3 -m compileall scripts/ -q` if you want stdout-only compile without pytest |
| **§1–2** Setup / configure | `test_e2e_flow.py` (setup `--defaults`, configure, validate); `vault_flow.test.py`; `test_error_paths.py` (config edge cases) | Interactive setup (`-i`), custom `--vault` path, git init on setup — spot-check |
| **§3–4** Ingest / raw | `vault_flow.test.py`; `test_adapters.py`, `test_dedup.py`, `test_tagger.py`, `test_pipeline.py`; `test_error_paths.py` | Full security-scan matrix, git snapshot on ingest, every raw flag — spot-check |
| **§5** Validate / lint | E2E + `vault_flow` wikilinks; `test_error_paths.py` | `list-topics` — covered indirectly; confirm with CLI if desired |
| **§6** Search backends | `test_mcp.py` (FTS5, grep, chroma/hybrid where deps exist) | Every fallback combination on every OS — spot-check |
| **§7** Knowledge graph | `test_mcp.py` KG helpers; E2E `kg add/query/stats` | SQLite backend variants — `test_mcp.py` / CLI spot-check |
| **§8** Session memory | `test_session_memory.py`; E2E memory save/list/recall/show | Prune edge cases, bad metadata — spot-check |
| **§9** Git | `test_mcp.py` or dedicated git tests if present — **partial** | Full git matrix (§9) — manual or expand tests |
| **§10** MCP | `test_mcp_contract.py` (stdio JSON-RPC); `test_mcp.py` (tools/search) | **§10b** SSE/HTTP server, port conflicts — manual; **§10.16–10.17** `mcp install` / `mcp start` — manual |
| **§11** Viewer | `test_viewer_playwright.py` (`@pytest.mark.browser`, `RUN_BROWSER_TESTS=1`): `build-site` → HTTP → Chromium loads `index.html` | Full search/D3/editor UX — manual |
| **§12** Graph CLI | E2E + `vault_flow` `graph --out` | `graph --mode knowledge`, empty wiki — partially in other tests; spot-check |
| **§13–15** Research / benchmarks / metrics | `test_benchmark.py`, `test_locomo_convomem_suites.py`, `test_lme_failure_qids.py`; E2E `metrics stats` | Full benchmark suites with real data paths — opt-in / CI |
| **§16** Agent docs | `sync_agent_docs.test.py` | Deliberate drift test (§16.3) — manual destructive check |
| **§17** Plugin manifests | `plugin_contracts.test.py` (commands/skills/adapters) | `integrations wizard`, live API validate — manual |
| **§18** Error paths | `test_error_paths.py`, `url_safety.test.py` | Permission-denied, concurrency, 10MB files — manual or future tests |
| **§19** CLI help | `cli_help.test.py` (every subcommand `--help`) | `unknown subcommand` UX — spot-check |
| **§20** Hooks | `test_hooks.py` (needs `jq`); `test_hooks_inventory.py` (`hooks.json` paths + `bash -n` on `hooks/*.sh`) | Real IDE hook triggers — manual |
| **§21** Slash commands | `plugin_contracts.test.py` (command files + skills) | Prompt quality — manual |
| **§22** Skills (agent) | Tier **7** `test_skill_evals.py` + `skill_eval_cases.py` (`RUN_CLAUDE_TESTS=1`); `test_plugin_inventory.py` (every `wiki-*` skill in `SKILL_EVALS` or `SKILL_EVAL_EXCLUDE`); optional Codex mirror | Full product slash-command UX — manual |
| **§23** E2E scenario | `test_e2e_flow.py` mirrors the script (including final `validate`, `check`, then `teardown --purge`) | — |
| **§24** Regression | Same as §0 + §23 + MCP/hooks/replay | Periodic §11/§10b manual passes before release |
| **Inventory** | `test_hooks_inventory.py` + `test_plugin_inventory.py` (default `smoke-test`) | — |

**Markers:** `pytest -m network` (opt-in), `-m replay` (golden only), `-m claude` (skill evals, opt-in), `-m browser` (Playwright viewer, opt-in). Env: `RUN_MINIMAL_SKILL_EVALS=1` shrinks Claude/Codex skill evals to three core cases (stderr banner when set).

---

## 27 — Automation levels (programmatic vs manual)

**Can every playbook row be automated?** **No.** Some checks require a **browser**, **user home files**, **live credentials**, **interactive TTY**, or **destructive** side effects. The project goal is **strong programmatic coverage** for deterministic behavior plus an explicit **manual tier** for the rest — not a brittle 1:1 mapping of §1–§24 to pytest.

### Levels (use these names in CI and release notes)

| Level | Command | What is asserted | Typical use |
|-------|---------|------------------|-------------|
| **L0 — Default gate (required)** | `bin/llm-wiki smoke-test -v` | Full offline pytest: contracts, CLI `--help`, vault flows, E2E (`test_e2e_flow.py`), hooks (`jq`), MCP stdio contract, golden replay, adapters, error paths, session memory, benchmarks that do not need network — **see §26**. CI also runs **retrieval-smoke** (LME `--limit 10`, no LLM) on PRs/pushes. | **Required** every PR / push |
| **L0b — Replay only** | `bin/llm-wiki smoke-test --replay` | Golden CLI fixtures only (`@pytest.mark.replay`) | Quick regression on parser/CLI changes |
| **L1 — Network opt-in** | `RUN_NETWORK_TESTS=1 bin/llm-wiki smoke-test --network` or `pytest -m network` | HTTPS reachability (`tests/network.test.py`) | Environments that allow egress |
| **L2 — Agent CLI (Claude, full skill eval)** | `RUN_CLAUDE_TESTS=1 bin/llm-wiki smoke-test --claude` | `claude plugin validate` (when enabled) + full `SKILL_EVALS` in `tests/skill_eval_cases.py` (`test_skill_evals.py`); needs Claude Code CLI + subscription/OAuth; `RUN_MINIMAL_SKILL_EVALS=1` limits to three core cases | **Optional** (scheduled/manual CI when `ANTHROPIC_API_KEY` is set; recommended before major releases) |
| **L2b — Codex skill mirror** | `RUN_CODEX_SKILL_EVALS=1 pytest tests/test_skill_evals_codex.py -v` | Same scenarios via `codex exec` | Optional second agent (pre-ship: optional; skip if no Codex) |
| **L2c — Browser / viewer smoke** | `RUN_BROWSER_TESTS=1 bin/llm-wiki smoke-test --browser` | Playwright loads built static viewer (`@pytest.mark.browser`) | Pre-ship or machines with Chromium installed |
| **L2d — Full inventory (deterministic)** | Included in **L0** (`test_hooks_inventory.py`, `test_plugin_inventory.py`) | `hooks.json` ↔ `hooks/*.sh`; every `wiki-*` skill in `SKILL_EVALS` or `SKILL_EVAL_EXCLUDE`; `bash -n` on hooks | Re-run explicitly before release if desired |
| **L3 — Manual / product** | Checklists **§11** (full UI), **§10b** (SSE), **§10.16–17** (`mcp install`), interactive **§1.2 / §2.2**, live **integrations validate** | Human or dedicated E2E infrastructure | Release candidate, marketplace submission |

### What is intentionally *not* fully programmatic

| Reason | Examples (playbook) |
|--------|---------------------|
| **Browser / DOM** | §11 viewer (search, D3 graph, “Open in editor”) |
| **Writes outside repo** | §10.16 `mcp install` → `~/.claude/`, `./mcp.json` |
| **Long-lived processes / ports** | §10b SSE server, §10.17 background MCP |
| **Secrets / billing** | §17 live API validation; any row requiring real provider keys |
| **Interactive UX** | Setup/configure wizards (`-i`) |
| **Subjective** | §21–§22 “prompt quality”, agent strategy in real Claude/Cursor |

### Growing automation safely

Add **new pytest tests** when a case is **deterministic** (subprocess, `tmp_path`, no network). Keep **manual** rows for UI and environment-specific checks. When you add a test, update **§26** so the matrix stays truthful.

### Pre-ship deep test (release candidate)

**L0 is the required gate** for every PR/push (pytest + plugin-repo check + retrieval-smoke). A **retrieval-smoke SKIPPED** summary (network/download failure) is **not** an L0 pass — re-run when Hugging Face is healthy. **L2 (Claude skill eval) is optional** — the skill-evals workflow is **skipped** without `ANTHROPIC_API_KEY` (not a false-green run); recommended before a major release, not a hard merge blocker.

Before a release or marketplace submission, prefer this order:

1. **Deterministic / gate (L0 + §0) — required:** `bin/llm-wiki smoke-test -v`, `bin/llm-wiki sync-agent-docs --check`, `bin/llm-wiki check --plugin-repo` (includes **L2d** inventory tests: `test_hooks_inventory.py`, `test_plugin_inventory.py`). Confirm CI **retrieval-smoke** (or run `benchmark run lme --limit 10` + `benchmarks/compare_ci_baseline.py` locally).
2. **Inventory spot-check (optional):** `python -m pytest tests/test_plugin_inventory.py tests/test_hooks_inventory.py -v` if you want an explicit re-run.
3. **Browser (L2c) — optional / recommended:** `RUN_BROWSER_TESTS=1 bin/llm-wiki smoke-test --browser` after `pip install playwright` and `playwright install chromium`.
4. **Claude skill eval (L2) — optional:** `RUN_CLAUDE_TESTS=1 bin/llm-wiki smoke-test --claude` (full `SKILL_EVALS` + `claude plugin validate` when applicable). Do **not** set `RUN_MINIMAL_SKILL_EVALS` for a serious pre-ship pass. Skip and record why if no API key / Claude CLI.
5. **Codex mirror (L2b) — optional:** `RUN_CODEX_SKILL_EVALS=1 pytest tests/test_skill_evals_codex.py -v` — skip if you do not use Codex.
6. **Network (L1) — optional:** `RUN_NETWORK_TESTS=1 bin/llm-wiki smoke-test --network` if egress matters for this release.

**Promptfoo:** not wired in this repo. Treat any Promptfoo harness as a **future optional** eval layer only — do not block L0/CI on it.

**Dev shortcut:** `RUN_MINIMAL_SKILL_EVALS=1` with `--claude` runs only wiki-query / wiki-status / wiki-session-memory (stderr banner when set).

When any of **L1 / L2 / L2b / L2c** (or `RUN_MINIMAL_SKILL_EVALS` / `RUN_CODEX_SKILL_EVALS`) apply, pytest / `smoke-test` prints a short **stderr banner** so logs show cost-bearing tiers.

---

## Version history

| Date | Change |
|------|--------|
| 2026-04-09 | Initial playbook covering all CLI, MCP, skill, and integration tests |
| 2026-04-10 | §25 automation harness (tiers, golden replay, recording, cleanup) |
| 2026-04-10 | Skill eval scenarios in `tests/skill_eval_cases.py`; Claude default; optional Codex in `test_skill_evals_codex.py` (`RUN_CODEX_SKILL_EVALS=1`) |
| 2026-04-10 | `claude_runner` / `qa_record`: `--add-dir` vault + `--` before prompt; QAPLAYBOOK portable `claude -p` example (`$REPO_ROOT`, no hardcoded paths) |
| 2026-04-10 | §26 coverage matrix; E2E final `validate`+`check`; `test_check_plugin_repo_cli_matches_qa_gate` for §0.3 |
| 2026-04-10 | §27 automation levels (L0–L3): programmatic vs manual; what cannot be CI-asserted |
| 2026-04-10 | Tier 8 / L2c: `test_viewer_playwright.py`, `smoke-test --browser`, `RUN_BROWSER_TESTS`; `test_hooks_inventory.py`; stderr banners; pre-ship checklist (Claude required, Codex optional) |
| 2026-04-10 | L2d/L2e: `test_plugin_inventory.py`; expanded `SKILL_EVALS` + `SKILL_EVAL_EXCLUDE`; `skill_eval_cases_for_run` + `RUN_MINIMAL_SKILL_EVALS`; pre-ship doc order (inventory → browser → Claude → Codex → network) |
| 2026-07-28 | Align tiers: **L0 required** (incl. retrieval-smoke); **L2 optional**; Promptfoo noted as future optional only |
