---
description: Run retrieval benchmarks (LME / LoCoMo / ConvoMem) from the vault; optional LLM rerank via API or local CLI.
---

# Benchmark retrieval

Run **`llm-wiki benchmark`** against the configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`). See **`benchmarks/README.md`** for methodology and scores.

## Quick usage

From **repo root** (or use absolute path to `bin/llm-wiki`):

```bash
llm-wiki benchmark run lme --backend fts5 --compress raw --limit 20
```

**Peer backends (same LME JSON):** `llm-wiki benchmark run lme --peer mem0 --limit 10` — optional **mem0**, **mempalace**, **claude-mem**, **supermemory** (see **`benchmarks/README.md`**). Use **`--strict-peers`** to fail when a peer cannot run.

LLM rerank (closes most LME gaps): set **`benchmark.search.rerank_llm.enabled`** to true **or** export **`LLM_WIKI_BENCHMARK_LLM=1`**, and configure **`invoke`**:

| `invoke` | Auth |
|----------|------|
| **`anthropic_api`** (default) | **`ANTHROPIC_API_KEY`** (or `.env` / `.env.local` loaded by the CLI) |
| **`claude_cli`** | Local **`claude`** CLI (prompt on stdin; default argv `claude -p -`) |
| **`codex_cli`** | Local **`codex`** CLI (override **`cli_argv`** if your install differs) |
| **`custom_cli`** | Set **`cli_argv`** to a full argv list ending with `-` for stdin |

**MCP:** If the vault MCP server is connected, call tool **`wiki_benchmark_run`** with `suite`, `limit`, `backend`, `compressor`, optional **`use_llm`**: true to set `LLM_WIKI_BENCHMARK_LLM=1`, and optional **`peers`**: e.g. `["mem0"]` for peer LME.

## Arguments

$ARGUMENTS

## Smoke check

- **CLI:** Run `llm-wiki benchmark run lme --limit 3` from repo root; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, use **`/llm-wiki:benchmark`** (or run the CLI above) and verify the command completes without errors.
- **MCP:** `tools/list` includes **`wiki_benchmark_run`**.
