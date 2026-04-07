---
name: wiki-lint
description: Audits llm-wiki/wiki for orphans, stale claims, missing links, and contradictions. Use when user asks to health-check the wiki.
---

# Wiki lint

For **ingested `raw/`** that is still structurally broken before wiki merge, use **`wiki-raw-prepare`** / **`llm-wiki raw validate`** first; **wiki-lint** focuses on **`wiki/`** coherence.

1. Scan **`wiki/index.md`** vs actual pages; list **orphans** (unindexed) and **broken wikilinks**.
2. Note **contradictions** between pages (different claims about the same entity).
3. Suggest **next sources** or questions to resolve gaps.
4. If **`outputs/`** exists, flag **contradictions** or **duplicate claims** between **outputs/** and **wiki/** (treat outputs as drafts until promoted with evidence).

Optional: `skills/references/context-persona.md` when running checks via tools; `persona.name` in config (default **Gennie**).
