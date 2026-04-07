---
description: Validate and clean raw markdown after ingest; log preparation goals; commit with prepare phase.
---

1. **LLM / editor:** Clean up the extracted **`raw/`** file (structure, headings, noise). Respect **ingestion_security** if flagged.
2. **Deterministic pass:** **`llm-wiki raw validate <path> --autofix`** (or skip to step 3).
3. **One-shot (recommended):** **`llm-wiki raw finish <path> -m "short description of what changed"`** → autofix + validate + append **`raw/.preparation-log.jsonl`** + vault **git commit** with **`[prepare]`** prefix (needs **`git.enabled`**). Use **`--record-action llm_cleaned`** after heavy LLM edits; **`--skip-git`** to log only.
4. **Or:** separate **`raw record`** + **`git snapshot --phase prepare`** as in **wiki-raw-prepare** skill.
5. Then **wiki-ingest** to merge into **`wiki/`**.

User intent: $ARGUMENTS
