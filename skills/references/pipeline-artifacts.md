# Vault pipeline — feed-forward artifacts

Companion to **wiki-pipeline**. Each stage **writes** artifacts the next stage **reads**. Paths are relative to the vault root (`llm-wiki/` by default).

| Stage | Skill / command | Writes | Read by |
|-------|-----------------|--------|---------|
| status | **wiki-status** | Health report (stdout); no required file | pipeline gate: stop if setup incomplete |
| research | **wiki-research** or **wiki-fetch** | `raw/<type>/<slug>.md` with frontmatter | prepare, ingest |
| prepare | **wiki-raw-prepare** / `llm-wiki raw finish` | Cleaned `raw/` files (excludes **`raw/memory/`**); **`raw/.preparation-log.jsonl`** | ingest |
| memory (auto) | Claude Code hooks + `llm-wiki memory …` | **`raw/memory/<session-id>.md`** | recall, ingest (optional), search index |
| ingest | **wiki-ingest** + **wiki-maintainer** | `wiki/**/*.md`, **`wiki/index.md`**, **`wiki/log.md`** | kg update, lint, compile, build |
| kg update | `llm-wiki kg rebuild` (if `knowledge_graph.auto_update_on_ingest`) | `.kg.json` or `.kg.sqlite3` | query (via MCP or CLI) |
| lint | **wiki-lint** / `llm-wiki lint` | **`outputs/lint-report.json`**, **`outputs/claims.json`** | pipeline gate |
| compile | `llm-wiki compile` / MCP **`wiki_compile`** | lint + KG conflicts + optional site; surgical **`--raw`** | ship / search |
| build | `llm-wiki build-site` (or folded into **compile**) | **`wiki/.og/`** static viewer | validate |
| validate | `llm-wiki validate` / `validate --wikilinks` / `knowledge-test` | Pass/fail (stdout) | done |

**Notes**

- **`outputs/`** holds drafts (e.g. deep research). Promote to **`wiki/`** only after review; **wiki-lint** can compare **`outputs/`** vs **`wiki/`**.
- Vault git phases (`[ingest]`, `[prepare]`, `[wiki]`, …) align with **`llm-wiki git lifecycle`**; see **`WORKFLOWS.md`**.
- After **`llm-wiki ingest`** finishes **`post_ingest`** on a `raw/` file, **`knowledge_graph.auto_update_on_ingest`** triggers **`llm-wiki kg rebuild`** automatically (same triple store as manual wiki-merge path).
