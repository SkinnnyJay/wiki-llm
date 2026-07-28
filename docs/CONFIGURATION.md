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


# Configuration

**Order:** **Claude Code** → **CLI** → **config file** details.

<a id="configuration-full"></a>

## 1. Claude Code

- **`/llm-wiki:configure`** — guided tweaks to **`llm-wiki/config.json`** (same ideas as [`commands/configure.md`](../commands/configure.md)).

## 2. CLI

- **`llm-wiki configure -i`** — interactive edits from a terminal.

## 3. `config.json` (reference)

Toggles live in **`llm-wiki/config.json`**: viewer, integrations, git, research loop, ingestion security, optional hooks, and **`persona.name`** (default **Gennie**). For sound hooks, ingest policy, viewer serving, and git lifecycle, see **[`WORKFLOWS.md`](../WORKFLOWS.md)**.

### Quick reference

- **`config.json`** — `viewer` (including `open_file_scheme`, `og_base_url`), `integrations`, `git`, `research_loop`, `ingestion_security`, **`hooks.sound`**, **`persona.name`**.
- **Sound hook** — Optional `hooks.sound.enabled` + `hooks.sound.command` (argv JSON); restrict executables unless `allow_arbitrary_command` is set deliberately (see **WORKFLOWS**).
- **Ingest URLs** — `ingest url` / Firecrawl allow http(s) to public hosts only; integration hosts are allowlisted.
- **Viewer** — Serve `wiki/.og/` over HTTP; **DOMPurify** on rendered bodies; **Open file** via `viewer.open_file_scheme`.
- **Ingest paths** — `--out` must stay under `raw/`.
- **Wikilinks** — `[[Page]]` / `[[page.md|label]]`; general Markdown: [Markdown Guide](https://www.markdownguide.org/basic-syntax/).
- **Vault git** — With `git.enabled`, **`llm-wiki git lifecycle`** audits commits by phase; see [`commands/git-lifecycle.md`](../commands/git-lifecycle.md).

### Performance and large vaults

The defaults favor responsive local use. Tune them only after observing a
specific bottleneck:

- **`mcp.search_backend`** — `fts5` is the default local full-text index.
  `grep` avoids an index but scans files for every request. `chromadb` and
  `hybrid` add semantic retrieval and require the optional Chroma dependency.
- **`performance.sqlite`** — SQLite index settings: `journal_mode`,
  `synchronous`, `cache_size`, `mmap_size`, and `busy_timeout`. The default
  WAL + normal durability profile is suitable for most single-machine vaults.
- **`mcp.status_file_count_ttl_seconds`** — caches raw/wiki markdown counts
  returned by `wiki_status` (default: `45`). Increase it when a very large
  vault makes repeated status calls expensive; set it lower only when
  near-immediate count changes matter.
- **`mcp.max_response_chars`** — caps each MCP JSON response (default:
  `500000`; `0` is unlimited). Lower this to bound editor context and
  transport cost; use `mcp.read_page_max_chars` as an additional page-body
  limit.
- **`ingestion.max_download_bytes`** — maximum response body accepted by the
  built-in URL ingest adapter (default: `33554432`, or 32 MiB). Raise it only
  for trusted, legitimately large sources.

For large vaults, budget time for the first index build and for a full
reindex after broad raw/wiki changes. Keep generated index files on local
fast storage with `storage.search_db` (and, if used, `storage.chromadb_dir`);
run `llm-wiki search "<query>"` before changing backends to confirm the
current index is healthy. No automatic reindex SLA is assumed because it
depends on page count, disk speed, and the selected backend.

To build and open the static viewer in one command:

```bash
llm-wiki build-site --serve-background --open
```
