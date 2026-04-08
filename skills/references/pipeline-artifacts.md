# Vault pipeline — feed-forward artifacts

Companion to **wiki-pipeline**. Each stage **writes** artifacts the next stage **reads**. Paths are relative to the vault root (`llm-wiki/` by default).

| Stage | Skill / command | Writes | Read by |
|-------|-----------------|--------|---------|
| status | **wiki-status** | Health report (stdout); no required file | pipeline gate: stop if setup incomplete |
| research | **wiki-research** or **wiki-fetch** | `raw/<type>/<slug>.md` with frontmatter | prepare, ingest |
| prepare | **wiki-raw-prepare** / `llm-wiki raw finish` | Cleaned `raw/` files; **`raw/.preparation-log.jsonl`** | ingest |
| ingest | **wiki-ingest** + **wiki-maintainer** | `wiki/**/*.md`, **`wiki/index.md`**, **`wiki/log.md`** | lint, build |
| lint | **wiki-lint** | Issues (stdout); optional **`outputs/lint-report.md`** | pipeline gate |
| build | `llm-wiki build-site` | **`wiki/.og/`** static viewer | validate |
| validate | `llm-wiki validate` / `validate --wikilinks` | Pass/fail (stdout) | done |

**Notes**

- **`outputs/`** holds drafts (e.g. deep research). Promote to **`wiki/`** only after review; **wiki-lint** can compare **`outputs/`** vs **`wiki/`**.
- Vault git phases (`[ingest]`, `[prepare]`, `[wiki]`, …) align with **`llm-wiki git lifecycle`**; see **`WORKFLOWS.md`**.
