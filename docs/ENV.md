# Environment variables

**Copy [`../.env.example`](../.env.example)** to **`.env`** and/or **`.env.local`** in the **plugin repo root** (both are gitignored). The CLI loads **`.env`** then **`.env.local`** on startup (later file wins per key); values already set in your shell are **not** overwritten unless the key is empty — see [`scripts/lib/env_loader.py`](../scripts/lib/env_loader.py).

| Disable auto-load | Set `LLM_WIKI_SKIP_DOTENV=1` (or `true` / `yes`). |

**Claude Code:** you can mirror the same keys under **`env`** in **`.claude/settings.local.json`** (gitignored) or **`~/.claude/settings.json`** so tools and the IDE share credentials — see comments in `.env.example`.

---

## Vault and paths

| Variable | Purpose |
|----------|---------|
| **`LLM_WIKI_VAULT`** | Absolute path to the vault directory (`config.json`, `wiki/`, `raw/`). Used by the CLI when you are not passing `--vault` and not running from a directory that already resolves the vault. Also used by hooks (`hooks/*.sh`) and shell helpers (`scripts/serve-viewer.sh`, `serve-graph.sh`). |
| **`CLAUDE_PLUGIN_ROOT`** | Set by **Claude Code** to this plugin’s checkout. Used to find `bin/llm-wiki` in hooks. Not something you typically put in `.env` manually. |

Resolution order for the CLI: **`--vault`** → **`LLM_WIKI_VAULT`** → `./llm-wiki` (if `config.json` exists there) → current directory if it already looks like a vault → default `./llm-wiki`. See [`scripts/lib/paths.py`](../scripts/lib/paths.py).

**MCP trust and HTTP hardening** (tool surface, SSE bind, tokens) are documented in [`skills/references/mcp-and-kg.md`](../skills/references/mcp-and-kg.md) — not env vars; use **`llm-wiki/config.json`** under `mcp.*`.

---

## Integrations (ingest / search)

Defaults use the names below; each integration in **`llm-wiki/config.json`** can override with **`api_key_env`**.

| Variable | Used for |
|----------|----------|
| **`BRAVE_SEARCH_API_KEY`** | Brave Search adapter (`brave`), research-loop search fan-out |
| **`FIRECRAWL_API_KEY`** | Firecrawl adapter (`firecrawl`) — REST or CLI |
| *(none)* | **`playwright`** ingest adapter — install **`playwright`** Python package and run **`playwright install chromium`**; no API key. Optional **Playwright MCP** in the editor is separate from vault MCP. |
| **`PERPLEXITY_API_KEY`** | Perplexity adapter (`perplexity`) |
| **`TWITTER_AUTH_TOKEN`** | Twitter/X adapter (`twitter`) with bird CLI |
| **`ANTHROPIC_API_KEY`** | PDF vision ingest, pdf-marker / MarkItDown LLM paths, benchmark rerank when configured for Anthropic |
| **`OPENAI_API_KEY`** | MarkItDown OpenAI path, embeddings, benchmark rerank when configured for OpenAI |
| **`GOOGLE_API_KEY`** | pdf-marker Gemini path (alias: **`GEMINI_API_KEY`**) |

---

## PDF marker subprocess

| Variable | Purpose |
|----------|---------|
| **`LLM_WIKI_MARKER_BLOCK_PROMPT`** | Optional override for marker PDF LLM block prompt (see [`scripts/ingest/adapters/_marker_subprocess.py`](../scripts/ingest/adapters/_marker_subprocess.py)). |

---

## Benchmarks

| Variable | Purpose |
|----------|---------|
| **`LLM_WIKI_BENCHMARK_LLM`** | Set to `1` / `true` / `yes` to enable LLM-based reranking during benchmark runs (also toggled via config and MCP in some paths). |
| **`LLM_WIKI_BENCHMARK_DEBUG_RERANK`** | Debug logging for LME rerank (see [`benchmarks/lme_bench.py`](../benchmarks/lme_bench.py)). |

`research_loop` / **`benchmark.search.rerank_llm.invoke`** may use **`api_key_env`** in config (often `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`). See [`benchmarks/README.md`](../benchmarks/README.md) and [`commands/benchmark.md`](../commands/benchmark.md).

---

## Pytest and `smoke-test`

Opt-in suites (set to `1`, `true`, or `yes`):

| Variable | Enables |
|----------|---------|
| **`RUN_NETWORK_TESTS`** | `@pytest.mark.network` |
| **`RUN_CLAUDE_TESTS`** | `@pytest.mark.claude` (Claude CLI + skill evals) |
| **`RUN_CODEX_SKILL_EVALS`** | `@pytest.mark.codex_skill_eval` |
| **`RUN_BROWSER_TESTS`** | `@pytest.mark.browser` (Playwright) |
| **`RUN_MINIMAL_SKILL_EVALS`** | Shrinks skill evals to three core cases only |
| **`RUN_RERANK_SMOKE`** | Optional rerank smoke tests (`tests/test_rerank_llm_smoke.py`) |

Or use **`bin/llm-wiki smoke-test --network`**, **`--claude`**, **`--browser`** (sets the corresponding `RUN_*` vars). See [`docs/QAPLAYBOOK.md`](./QAPLAYBOOK.md) §25–27.

---

## Claude skill-eval harness and `qa_record.py`

Used when running **`claude -p`** tests or **`scripts/qa_record.py`** (not for normal vault CLI use):

| Variable | Purpose |
|----------|---------|
| **`CLAUDE_RUNNER_SETTING_SOURCES`** | Passed to `claude -p` as `--setting-sources` (default in tests: `project`). |
| **`CLAUDE_RUNNER_KEEP_ANTHROPIC_ENV`** | If set, do not strip `ANTHROPIC_*` from the subprocess env (tests default to stripping so API keys from `.env` do not force API billing). |
| **`SKILL_EVAL_BACKEND`** | Test fixture backend selection in [`tests/conftest.py`](../tests/conftest.py) (default `claude`). |

The subprocess strip list includes **`ANTHROPIC_API_KEY`** and **`ANTHROPIC_AUTH_TOKEN`** — see [`scripts/lib/claude_env.py`](../scripts/lib/claude_env.py).

---

## Hooks (Claude Code)

| Variable | Purpose |
|----------|---------|
| **`LLM_WIKI_CLEANUP_NPX`** | If `1`, SessionEnd hook sends SIGTERM to stray `npx` / plugin `node_modules` processes for this checkout only. See [`hooks/README.md`](../hooks/README.md). |

Hooks also honor **`LLM_WIKI_VAULT`** and **`CLAUDE_PLUGIN_ROOT`** as above.

---

## Optional extract / research skills

Network-heavy or niche keys are documented on each skill. Examples (not an exhaustive runtime list — see the matching **`skills/wiki-*/SKILL.md`**):

| Variable | Skill / area |
|----------|----------------|
| **`ANNAS_ARCHIVE_KEY`** | wiki-extract-annas |
| **`CRUNCHBASE_API_KEY`** | wiki-extract-crunchbase |
| **`GITHUB_TOKEN`** | wiki-extract-github |
| **`PODCAST_INDEX_KEY`**, **`PODCAST_INDEX_SECRET`** | wiki-extract-podcast |
| **`ASSEMBLYAI_API_KEY`** | wiki-extract-podcast (transcription) |
| **`NEWS_API_KEY`** | wiki-setup wizard / NewsAPI (optional) |
| **`AMAZON_PA_API_KEY`** | wiki-extract-ecommerce (optional PA API) |
| **`ASIN`** | Example shell variable in ecommerce skill (product id), not always required |

---

## Session memory (`memory.enabled`)

Session files live under **`raw/memory/`** (see **`memory.dir`** in `llm-wiki/config.json`). This is **not** configured via a dedicated env var — enable the feature in config and use hooks + **`llm-wiki memory …`**.

| Topic | Notes |
|-------|--------|
| **`memory recall` quality** | Uses the same search stack as the rest of the vault (**`mcp.search_backend`**: fts5 / grep / chromadb / hybrid). Keyword-heavy notes work well with **fts5**; vague or conceptual queries benefit from **chromadb** or **hybrid** (optional pip install). |
| **Privacy / git** | If the vault is committed to git, **`raw/memory/*.md`** can be tracked like any other file. **Do not** store secrets, API keys, or private credentials in session notes — use gitignored tooling (e.g. `.claude/settings.local.json`) for keys instead. |
| **`memory.max_sessions`** | When set to a **positive** integer, **`memory save`** and **`memory log`** automatically delete the **oldest** session files (by modification time) so the count stays at or below the cap. **`0`** means unlimited (no automatic deletion). |

**Naming note:** Retrieval benchmark docs under **`docs/memory/benchmarks/`** are about **evaluation methodology** (LME, LoCoMo, etc.), not this session-memory feature — see that folder’s README.

---

## See also

- [`.env.example`](../.env.example) — copy-paste template
- [`docs/QAPLAYBOOK.md`](./QAPLAYBOOK.md) — CI vs manual tiers
- [`skills/references/preflight.md`](../skills/references/preflight.md) — integration preflight patterns
- [`commands/integrations.md`](../commands/integrations.md) — `llm-wiki integrations`
