# MCP Server, Search Backends, and Knowledge Graph — Shared Reference

Companion to **wiki-setup**, **wiki-status**, **wiki-query**, **wiki-ingest**, and **wiki-pipeline**. Reference this file instead of duplicating MCP/KG details in each skill.

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
    "hybrid_rrf_k": 60
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

**Benchmarks:** MCP tool **`wiki_benchmark_run`** runs LME / LoCoMo / ConvoMem against the vault (same as `llm-wiki benchmark run …`). Use **`use_llm`**: true to enable LLM rerank for that run per `benchmark.search.rerank_llm` (API or CLI `invoke`). Prefer the **CLI** when you have a shell (`llm-wiki benchmark run …`).

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
llm-wiki mcp install                   # Register stdio server in ~/.claude/… and ./mcp.json
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
| **Entity KG** | `llm-wiki kg query/stats/rebuild` | Structured triples (entity → relationship → target) extracted from wiki content |

These are complementary: the wikilink graph shows page-level connectivity; the entity KG stores fact-level relationships.
