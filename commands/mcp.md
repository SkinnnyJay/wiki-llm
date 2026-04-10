---
description: MCP server + editor config — stdio JSON-RPC (default) or HTTP transport; search/KG backends per llm-wiki/config.json.
---

# MCP server

Expose vault tools to agents via the **Model Context Protocol**. Prefer **CLI** when you have a shell (`skills/references/mcp-and-kg.md` § "CLI > MCP when local").

## Quick usage

```bash
llm-wiki mcp                              # stdio JSON-RPC (default for Claude/Cursor MCP)
llm-wiki mcp --transport sse --port 8891   # HTTP: POST / or /mcp with JSON-RPC body
llm-wiki mcp start                         # ensure HTTP listener is up (background if needed)
llm-wiki mcp install                       # Write ~/.claude/claude_desktop_config.json + ./mcp.json
```

`mcp.enabled` must be **`true`** in **`llm-wiki/config.json`** or the server exits. Search backend: **`mcp.search_backend`** (`fts5` | `grep` | `chromadb` | `hybrid`). For **`hybrid`**, optional **`mcp.hybrid_rrf_k`** (default **60**) sets reciprocal-rank fusion; Chroma must be installed or search falls back to **fts5**. **`wiki_status`** also reports **`search_backend_fallback`** and optional **`storage_warnings`** when absolute **`storage.*`** paths point outside the vault. Knowledge graph: **`knowledge_graph.backend`** (`json` | `sqlite`). Full reference: **`skills/references/mcp-and-kg.md`**.

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run `llm-wiki mcp --help` from the repo root; optionally `llm-wiki mcp install` and confirm a JSON-RPC line to stdio works.
- **Prompt:** In Claude Code with this plugin loaded, run **`/llm-wiki:mcp`** if registered; otherwise use the commands above.
