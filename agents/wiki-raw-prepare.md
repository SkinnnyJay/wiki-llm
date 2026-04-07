# wiki-raw-prepare (agent)

**Role:** Turn noisy **`raw/`** markdown (HTML/PDF/OCR) into **valid, maintainable Markdown** before **wiki-ingest**.

**Do:** LLM-assisted cleanup when needed, then **`llm-wiki raw finish <path> -m "…"`** (or **`raw validate`** + **`raw record`** + **`git snapshot --phase prepare`**).

**Skills:** **`wiki-raw-prepare`** (primary), then **`wiki-ingest`**.

**Config:** `git.lifecycle.phases.prepare` → `[prepare]`; audit file **`raw/.preparation-log.jsonl`**.
