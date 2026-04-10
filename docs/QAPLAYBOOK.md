# QA Playbook — wiki-llm

Manual test suite for verifying the full plugin flow before releases.
Run through each section after significant changes; mark pass/fail in your notes.

> **Quick smoke:** `bin/llm-wiki smoke-test -v` runs the full pytest suite (contracts, CLI help, vault flow, E2E, hooks, MCP stdio, golden replay). See **§25** for tiers and recording.
> This playbook also covers **manual** steps (viewer UI, marketplace install, cross-tool parity) that are not fully automated.

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
| 10.5 | wiki_ingest tool | Send `wiki_ingest` with adapter + args | Ingests; returns result |
| 10.6 | wiki_validate tool | Send `wiki_validate` | Returns validation status |
| 10.7 | wiki_kg_query tool | Send `wiki_kg_query` with entity | Returns KG triples |
| 10.8 | memory_save tool | Send `memory_save` | Saves session memory |
| 10.9 | memory_recall tool | Send `memory_recall` with query | Returns matching memories |
| 10.10 | wiki_benchmark_run | Send `wiki_benchmark_run` with suite | Runs benchmark; returns metrics |

### 10b — SSE/HTTP transport

| # | Test | Steps | Pass criteria |
|---|------|-------|---------------|
| 10.11 | Start SSE server | `bin/llm-wiki mcp --transport sse --port 8891` | Server listening on 127.0.0.1:8891 |
| 10.12 | HTTP POST / | `curl -X POST http://127.0.0.1:8891/ -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'` | JSON-RPC tools list response |
| 10.13 | HTTP POST /mcp | Same as above but to `/mcp` | Same response |
| 10.14 | Invalid JSON body | POST garbage body | HTTP 400 |
| 10.15 | Port already in use | Start SSE on occupied port | Error message, exit 1 |

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
| 11.4 | Serve viewer | `cd llm-wiki/wiki/.og && python3 -m http.server 8890` → open browser | Page loads; file tree visible; D3 graph renders |
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
| 12.6 | Serve graph | `python3 -m http.server 8890` in graph output dir → open browser | Interactive graph renders |

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
| 16.1 | Sync (generate) | Edit `docs/AGENTS.shared.md` → `bin/llm-wiki sync-agent-docs` | `AGENTS.md`, `CLAUDE.md`, `rules/llm-wiki.mdc`, `.claude/rules/llm-wiki.md` updated |
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
| 21.1 | setup | `commands/setup.md` | References `bin/llm-wiki setup` |
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
| 7 | Agent skill evals (`tests/test_skill_evals.py`) | `RUN_CLAUDE_TESTS=1 bin/llm-wiki smoke-test --claude` | API usage |

**Golden replay**

- Committed fixtures live under `tests/fixtures/golden/*.json` (schema: `steps` with `argv`, optional `file_checks`, `purge_vault_after`).
- Run **only** replay-marked tests: `bin/llm-wiki smoke-test --replay` (equivalent to `pytest tests -m replay`).

**Record → extract (optional, one-time / when changing flows)**

1. `python3 scripts/qa_record.py --scenario <name>` (requires `claude` on PATH and credentials). Writes `tests/fixtures/recordings/*.jsonl` (gitignored).
2. `python3 scripts/qa_extract_fixture.py tests/fixtures/recordings/<file>.jsonl -o tests/fixtures/golden/<name>.json`
3. Review and edit the JSON; commit the golden file.

**Claude CLI isolation (for evals and recording)**

Use `claude -p --bare --no-session-persistence --dangerously-skip-permissions --max-budget-usd <n>` so sessions are not persisted to disk and spend is capped. The harness in `tests/conftest.py` (`claude_runner`) follows this pattern. For maximum isolation, run with `HOME` pointing at a temp directory (optional).

**Cleanup**

- Pytest `tmp_path` removes per-test vaults.
- E2E and golden replay tests end with `teardown --purge --yes` where applicable.
- Session finalizer in `tests/conftest.py` prunes dead `~/.claude/sessions/*.json` locks and empty `~/.claude/session-env/` dirs after the test session.

---

## Version history

| Date | Change |
|------|--------|
| 2026-04-09 | Initial playbook covering all CLI, MCP, skill, and integration tests |
| 2026-04-10 | §25 automation harness (tiers, golden replay, recording, cleanup) |
