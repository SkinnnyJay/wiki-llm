---
description: Ad-hoc research on a topic — discover sources, ingest into raw/, merge into wiki/, with stepped progress and logging (wiki-research skill).
---

Follow the **wiki-research** skill. This command is **topic-led**; for recurring batch fetches from **`research-tasks.json`**, use **`/llm-wiki:research-loop`** instead.

1. Confirm vault paths (`llm-wiki/`). Read **`wiki/index.md`** before adding pages.
2. Execute phases: **scope → plan sources → ingest to raw/ → optional raw-prepare → wiki merge → report**. Show progress between phases.
3. Append **`wiki/log.md`** with a **`research | …`** entry for this session.
4. Use **`llm-wiki ingest`** (and integrations per **`llm-wiki integrations status`**) as needed; then **wiki-ingest** / **wiki-maintainer**. Obey **ingestion_security** when enabled.

**Topic / instructions:** $ARGUMENTS
