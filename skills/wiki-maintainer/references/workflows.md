# Workflows (summary)

## Ingest (after raw file exists)

1. Open raw artifact; note `llm_wiki_security` in frontmatter if present.
2. Update entity/topic pages; add wikilinks.
3. Append `wiki/log.md`.

## Query

1. Scan `wiki/index.md`, open relevant pages.
2. Answer with path citations.

## Lint

Orphans, stale claims, missing cross-links, contradictions between pages.
