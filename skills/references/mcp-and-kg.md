# MCP Server, Search Backends, and Knowledge Graph — Shared Reference

Companion to **wiki-setup**, **wiki-status**, **wiki-query**, **wiki-ingest**, and **wiki-pipeline**. Reference this file instead of duplicating MCP/KG details in each skill.

---

## MCP implementation (stdlib server vs Python SDK)

The MCP server is **`scripts/mcp_server.py`**: **line-delimited JSON-RPC over stdio** (and optional HTTP via **`scripts/mcp_sse.py`**), **stdlib only** — no required `pip install` to run tools. That keeps marketplace installs and PEP 668–restricted environments workable.

The official **[Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk)** (`mcp` on PyPI) is the conventional choice for **new** MCP servers that already depend on packaging. This project keeps a **custom server** deliberately so the plugin does not add a hard MCP dependency; protocol updates are maintained in-tree. Revisit an SDK migration only if maintenance cost or host compatibility clearly outweighs zero-dependency installs.

### Protocol compatibility

The server advertises MCP **`2025-11-25`** for current clients. During `initialize`, a client that explicitly requests **`2024-11-05`** receives that legacy revision instead. This is intentional dual support while editor and SDK hosts migrate; it does **not** advertise a future date such as `2026-07-28`. Revisit the compatibility branch after supported hosts have adopted the current revision.

### Limits and notifications (stdio + HTTP)

| Transport | Limit |
|-----------|--------|
| **stdio** (`mcp_server.py`) | Each JSON-RPC line must be **≤ 32 MiB**; larger lines are logged and skipped. |
| **HTTP** (`mcp_sse.py`) | **`Content-Length`** must be **≤ 32 MiB**; otherwise **413** with a JSON-RPC error (body not read). |
| **Tool result size** | Config **`mcp.max_response_chars`** truncates the serialized JSON string returned from **`tools/call`**. |

**Notifications:** **`notifications/initialized`** and **`notifications/cancelled`** return **no JSON-RPC result** on stdio (no stdout line). On HTTP, the server responds with **204 No Content** (no body). **`notifications/cancelled`** carries **`params.requestId`** (and optional **`params.reason`**) per the [MCP cancellation](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities) spec. This server is **single-threaded** on stdio: it **cannot interrupt** a running tool handler; cancellation is acknowledged for protocol compatibility and logging.

**Logging:** Tool errors and several control paths log with **`mcp_request_id`**, **`mcp_method`**, **`mcp_tool`**, and **`mcp_cancelled_request_id`** (where applicable) in the **`extra`** dict for log aggregators, plus a human-readable **` \| key=value`** suffix in the message on stderr.

---

## CLI > MCP when local

| Context | Preferred | Why |
|---------|-----------|-----|
| Agent running **locally** (same machine as vault) | **CLI** (`llm-wiki kg …`, `llm-wiki validate`, etc.) | Direct, no server overhead, full exit codes and stdout |
| Agent running in an **editor plugin** (Cursor, Claude Desktop) | **MCP tools** (via registered server) | Editor manages the connection; tools appear in tool palette |
| Agent **without shell** or **HTTP-only** integration | **`llm-wiki mcp --transport sse`** (HTTP POST JSON-RPC on `host:port`) | Same tools as stdio; use when the client cannot spawn a subprocess |

**Rule of thumb:** If you can run `llm-wiki` in a shell, do that. Use MCP tools when the agent framework requires tool-call semantics (e.g., it has no shell access) or when the editor has already registered the MCP server and the tools are available in the tool palette.

Skills should always show the **CLI form first** and note the MCP equivalent parenthetically, not the other way around.

---

## MCP security model

**Trust boundary:** Any client that can invoke MCP tools on your machine has **vault-equivalent power**: read files under the vault, change `config.json`, trigger ingest (network/subprocess), mutate the knowledge graph and session memory, and run benchmarks (network/cache). Treat MCP like **shell access to the vault**.

**stdio (default):** The editor spawns `mcp_server.py`; exposure is limited to processes on your user session.

**HTTP (`--transport sse`):** The same tool surface is available over **plaintext HTTP** on `mcp.host`/`mcp.port`. Binding to **non-loopback** addresses exposes the vault to the LAN unless firewalled. Prefer **`127.0.0.1`**, use **`mcp.sse_require_loopback`** / **`mcp.sse_token`** (see config keys below), or put a reverse proxy with TLS in front for remote use.

**Secrets:** `wiki_read_page` can read **any path under the vault** (e.g. `config.json`). Do not store raw API keys in tracked files; use env vars (see [`docs/ENV.md`](../../docs/ENV.md)).

---

## Operational matrix (MCP tools)

Rough classification for operators — see `mcp.tools_mode` / `mcp.tools_allowlist` to restrict.

| Risk | Tools |
|------|--------|
| **Network / subprocess** (ingest adapters) | `wiki_ingest` — adapter + **`post_ingest`** (CLI parity: `force`, `force_security`, manual `tags`); gated by `integrations.<adapter>.enabled` and optional `mcp.ingest_enabled` |
| **Network / disk (benchmarks)** | `wiki_benchmark_run` (and dataset downloads) — hidden with `wiki_benchmark_suites` when `mcp.benchmark_tool_enabled` is false |
| **Config write** | `wiki_configure` — optional `mcp.configure_allowlist` limits keys |
| **Search index / site** | `wiki_reindex`, `wiki_build_site` (optional `if_stale`), `wiki_graph_build` (D3 bundle — writes under output dir) |
| **KG writes** | `wiki_kg_add`, `wiki_kg_invalidate`, `wiki_kg_rebuild` |
| **Session memory writes / deletes** | `memory_save`, `memory_log`, `memory_prune` |
| **Subprocess (git)** | `wiki_git_status` — read-only git; no arbitrary shell |
| **Read-mostly** | `wiki_wake_up`, `wiki_status`, `wiki_list_topics`, `wiki_validate`, `wiki_read_page`, `wiki_graph`, `wiki_search`, `wiki_find_related`, `wiki_search_index_status`, `wiki_kg_query`, `wiki_kg_timeline`, `wiki_kg_stats`, `wiki_raw_validate` (optional `autofix`), `wiki_metrics_stats`, `wiki_metrics_query`, `wiki_benchmark_suites`, `memory_list`, `memory_show`, `memory_recall` |

---

## Config keys

All settings live in `llm-wiki/config.json`:

```json
{
  "mcp": {
    "enabled": true,
    "transport": "stdio",
    "port": 8891,
    "host": "127.0.0.1",
    "search_backend": "fts5",
    "hybrid_rrf_k": 60,
    "tools_mode": "full",
    "tools_allowlist": [],
    "max_response_chars": 500000,
    "read_page_max_chars": 0,
    "configure_allowlist": [],
    "benchmark_tool_enabled": true,
    "ingest_enabled": true,
    "sse_require_loopback": true,
    "sse_token": "",
    "status_file_count_ttl_seconds": 45
  },
  "knowledge_graph": {
    "enabled": true,
    "backend": "json",
    "auto_update_on_ingest": true
  },
  "memory": {
    "enabled": false,
    "dir": "raw/memory",
    "max_sessions": 50
  }
}
```

**Optional hardening (`mcp.*`):** **`tools_mode`** — `full` (default), `read_only` (search/query/list tools only), or `custom` (only names in **`tools_allowlist`**; an empty allowlist behaves like **`read_only`**). **`max_response_chars`** — cap serialized JSON per tool result (`0` = unlimited). **`read_page_max_chars`** — truncate **`wiki_read_page`** body when `> 0` (the tool’s **`max_chars`** argument overrides). **`configure_allowlist`** — if non-empty, **`wiki_configure`** only allows listed keys; prefix rules end with `.` (e.g. `mcp.`). **`benchmark_tool_enabled`** — hide **`wiki_benchmark_run`** and **`wiki_benchmark_suites`** when `false`. **`ingest_enabled`** — hide **`wiki_ingest`** when `false`. **`sse_require_loopback`** — when `true`, HTTP MCP refuses to bind to non-loopback hosts. **`sse_token`** — when non-empty, HTTP clients must send **`Authorization: Bearer …`** or **`X-LLM-Wiki-Token`**. Plaintext HTTP; use a reverse proxy with TLS for untrusted networks. **`status_file_count_ttl_seconds`** — TTL for cached **`wiki_status`** raw/wiki `*.md` counts.

**Session memory (`memory.*`):** Opt-in. When `memory.enabled` is `true`, hooks and `llm-wiki memory …` write **`raw/memory/<session-id>.md`**. **`raw validate`** skips that directory; search still indexes it (`scope="memory"`). **`llm-wiki/.current-session`** stores the active session id for **`--current`**.

---

## Search backends

| Backend | Key | Dependencies | Ranking | Best for |
|---------|-----|-------------|---------|----------|
| **FTS5** | `fts5` | None (stdlib `sqlite3`) | BM25 | Default — fast ranked search, zero deps |
| **Grep** | `grep` | None (`rg` preferred, falls back to `re`) | None | Literal/regex queries, no index needed |
| **ChromaDB** | `chromadb` | `pip install chromadb` (see `requirements-optional.txt`) | Semantic similarity | Best retrieval quality, needs embeddings |
| **Hybrid** | `hybrid` | ChromaDB + FTS5 indexes | RRF fusion of BM25 + semantic | Strongest overall when Chroma is available |

**`mcp.hybrid_rrf_k`** (default `60`): reciprocal rank fusion constant for **`hybrid`** only — same idea as `benchmark.search.hybrid_k` in benchmarks.

**Graceful fallback:** If **`chromadb`** is configured but the package is missing or init fails, search falls back to **grep** (with a log warning). If **`hybrid`** is configured but Chroma is missing or init fails, search falls back to **`fts5`** (not grep). Switch to **`fts5`** in config for BM25 without extra dependencies.

### ChromaDB upgrades and on-disk compatibility

Chroma persists under **`storage.chromadb_dir`** (default **`.chromadb/`** in the vault). Major **`chromadb`** upgrades can change on-disk layout or client APIs. If search fails after upgrading the package: remove **`llm-wiki/.chromadb`** (or your configured directory), then run **`llm-wiki ingest`** / rebuild search so indexes are recreated. Pin **`chromadb`** in your venv (see **`requirements-optional.txt`**) to upgrade on your own schedule.

### Storage paths outside the vault

Relative **`storage.*`** paths resolve under the vault — separate vaults stay isolated. If you set an **absolute** path for **`chromadb_dir`** (or other storage keys) **outside** the vault, **`wiki_status`** may include **`storage_warnings`**: shared indexes across projects can cause cross-talk or one bad index affecting multiple vaults.

---

## Knowledge graph backends

| Backend | Key | Storage | Dependencies | Best for |
|---------|-----|---------|-------------|----------|
| **JSON** | `json` | `llm-wiki/.kg.json` | None | Default — human-readable, inspectable |
| **SQLite** | `sqlite` | `llm-wiki/.kg.sqlite3` | None (stdlib `sqlite3`) | Temporal validity (`valid_from`/`valid_to`), indexed queries |

Both backends expose the same CLI and MCP tools.

---

## CLI quick reference

### Knowledge graph (CLI — preferred locally)

```bash
llm-wiki kg query "Entity"       # Relationships for an entity
llm-wiki kg add "Entity" "rel" "Target" --source "wiki/page.md"
llm-wiki kg stats                # Entity/triple counts
llm-wiki kg rebuild              # Rebuild from all wiki/ pages
llm-wiki kg invalidate "Entity" "rel" "Target"
llm-wiki kg timeline "Entity"    # Temporal history
```

MCP equivalents: `wiki_kg_query`, `wiki_kg_add` (use when agent has no shell).

### Search (CLI — preferred locally)

```bash
# FTS5 ranked search via Python one-liner
python3 -c "
from scripts.lib.search import get_search_backend
from pathlib import Path
for r in get_search_backend(Path('llm-wiki')).search('query', limit=10):
    print(f'{r[\"score\"]:.2f}  {r[\"path\"]}')
"
```

MCP equivalent: `wiki_search` tool. Use when agent has no shell access. Pass **`scope: "memory"`** to search only session memory files.

**Benchmarks:** **`wiki_benchmark_run`** matches `llm-wiki benchmark run` (suite, limit, backend, compressor, **`top_k`**, optional **`data_path`** under vault or benchmark cache, **`no_metrics`**, **`use_llm`**). **`wiki_benchmark_suites`** returns the same help text as **`llm-wiki benchmark suites`**. Prefer the **CLI** for full matrix runs (`--backend all`, etc.).

**Metrics (read-only on MCP):** **`wiki_metrics_stats`** / **`wiki_metrics_query`** mirror **`llm-wiki metrics stats`** and **`metrics query`**; use the **CLI** for **`metrics record`**, **`clear`**, **`report`**, **`summary`**.

### Session memory (CLI — preferred locally)

```bash
llm-wiki memory save --current --summary "…" --tags research,ingest
llm-wiki memory list --json
llm-wiki memory show SESSION_ID
llm-wiki memory recall "alignment" --tag research --limit 5
llm-wiki memory prune --keep 20 --dry-run
```

MCP equivalents: `memory_save`, `memory_list`, `memory_show`, `memory_recall`, `memory_prune` (use when the agent has no shell). Requires **`memory.enabled`**.

### MCP server (for editors / HTTP clients)

```bash
llm-wiki mcp                           # stdio JSON-RPC (default; editor MCP)
llm-wiki mcp --transport sse --port 8891   # HTTP: POST / or /mcp with JSON-RPC body
llm-wiki mcp start                     # ensure HTTP listener is up (background if needed)
llm-wiki mcp install                   # Register in ~/.claude/… and plugin-root/.cursor/mcp.json
llm-wiki mcp install --project . --force  # Register in an explicit Cursor project
```

`--transport sse` uses **`mcp.host`** and **`mcp.port`** from config when `--port` / `--host` are omitted. **`mcp start`** probes that address and spawns **`mcp --transport sse`** in the background when nothing is listening (logs under **`llm-wiki/.mcp-sse.log`**).

---

## KG auto-update after ingest

When `knowledge_graph.auto_update_on_ingest` is `true`, the CLI runs **`kg rebuild`** after **`post_ingest`** (new `raw/` files) and skills should run it after merging into **`wiki/`** (**wiki-ingest**, **wiki-pipeline** stage 4b). Alternatively, add specific triples with `llm-wiki kg add` for key facts.

---

## Status checks (for wiki-status)

Report these in the health dashboard:

1. **MCP enabled?** — `mcp.enabled` in config
2. **Search backend** — which backend, whether index exists (**fts5**: `.search.sqlite3`; **chromadb**: `.chromadb/`; **hybrid**: both; **grep**: none). MCP **`wiki_status`**: `search_backend_fallback` when **chromadb**→grep or **hybrid**→fts5; optional **`storage_warnings`** if absolute **`storage.*`** paths sit outside the vault.
3. **KG enabled?** — `knowledge_graph.enabled` + backend type
4. **KG data** — entity/triple counts from `.kg.json` or `.kg.sqlite3`
5. **Editor registration** — is `llm-wiki` in `~/.cursor/mcp.json` or `~/.claude/claude_desktop_config.json`?
6. **Session memory** — `memory.enabled`; file count / size under `raw/memory/`; `memory.max_sessions`

---

## Setup wizard sections (for wiki-setup)

### MCP + search backend (Section 8)

Ask the user:

- **Defaults** — MCP on, FTS5 search *(recommended)*
- **Step-by-step** — choose search backend individually
- **Disabled** — skip MCP (agents use CLI commands instead)

If step-by-step: offer FTS5 / Grep / ChromaDB / Hybrid with the table above as explanation.

### Knowledge graph (Section 8b)

Ask the user:

- **JSON file** — zero-dep, `.kg.json` *(recommended)*
- **SQLite** — temporal validity, indexed queries
- **Disabled** — skip KG

### Session memory (Section 8c)

Ask the user:

- **Enable** — per-chat files in `raw/memory/`, hooks write `.current-session`
- **Disabled** — skip (default)

Optional: set `memory.max_sessions` for auto-prune after saves.

---

## Disambiguation: wikilink graph vs entity KG

| Feature | Command | What it does |
|---------|---------|-------------|
| **Wikilink graph** | `llm-wiki graph --mode knowledge` | D3 visualization of `[[wikilink]]` topology — clusters of connected pages |
| **Wikilink graph (MCP)** | `wiki_graph_build` | Same bundle as **`graph`** CLI; distinct from **`wiki_graph`** (JSON export for agents) |
| **Entity KG** | `llm-wiki kg query/stats/rebuild` | Structured triples (entity → relationship → target) extracted from wiki content |

These are complementary: the wikilink graph shows page-level connectivity; the entity KG stores fact-level relationships.
