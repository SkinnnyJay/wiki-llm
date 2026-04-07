---
description: Materialize sources into llm-wiki/raw/ then merge into the wiki per skills.
---

1. List adapters: `llm-wiki ingest --list`
2. Run the appropriate ingest, e.g.:

```bash
llm-wiki ingest file /path/to/doc.pdf --out raw/2026/doc.pdf
llm-wiki ingest url https://example.com/article --out raw/clips/article.md
llm-wiki ingest hackernews --limit 15
```

3. If `ingestion_security` is enabled, the CLI may flag prompt-injection patterns in raw files.
4. For HTML/PDF/OCR output that is not yet clean markdown, use **`/llm-wiki:raw-prepare`** (or **`wiki-raw-prepare`**) — `llm-wiki raw validate`, optional LLM cleanup, `llm-wiki raw record`, then git **`--phase prepare`** if enabled.
5. Apply **wiki-ingest** / **wiki-maintainer** skills: read `wiki/index.md`, update pages, append `wiki/log.md`.

User intent: $ARGUMENTS
