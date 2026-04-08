---
name: wiki-research-academic
description: Research academic papers from arXiv, DOI, or Semantic Scholar and ingest into raw/academic/. Invoked by wiki-research for paper requests.
user-invocable: false
---

# Wiki research — academic

Fetches academic papers and metadata from arXiv, DOI resolvers, or Semantic Scholar into `raw/academic/`. Use this sub-skill when the input contains an arXiv ID, DOI, or phrases like "paper", "preprint", "study", "literature review".

---

## Step 1 — Identify the source type

| Input signal | Action |
|-------------|--------|
| arXiv ID (e.g. `2301.12345` or `https://arxiv.org/abs/2301.12345`) | Fetch via arXiv API |
| DOI (e.g. `10.1145/3442188.3445922`) | Resolve via DOI → fetch landing page with wiki-research-web |
| Author + title search | Query arXiv API or Semantic Scholar search |
| Semantic Scholar URL | Fetch via Semantic Scholar API |

---

## Step 2 — Fetch paper metadata and content

### arXiv (primary for CS / ML / physics)

**Fetch metadata:**
```bash
curl "https://export.arxiv.org/api/query?id_list=<ARXIV_ID>&max_results=1" > /tmp/arxiv.xml
```

Parse from XML: `<title>`, `<author>`, `<published>`, `<summary>` (abstract), `<id>` (canonical URL), `<link>` (PDF).

**Fetch full paper (HTML version, preferred over PDF):**
```bash
llm-wiki ingest firecrawl "https://arxiv.org/html/<ARXIV_ID>" \
  --out academic/<year>/<arxiv-id>.md
# Fallback to abstract page if HTML not available:
llm-wiki ingest firecrawl "https://arxiv.org/abs/<ARXIV_ID>" \
  --out academic/<year>/<arxiv-id>.md
```

**Search by keyword:**
```bash
curl "https://export.arxiv.org/api/query?search_query=all:<QUERY>+AND+cat:cs.AI&max_results=10&sortBy=relevance" > /tmp/arxiv_search.xml
```
See `skills/wiki-research/references/query-design.md` for query construction.

### DOI resolver

```bash
# Resolve DOI to landing URL
curl -sI "https://doi.org/<DOI>" | grep -i location
# Then fetch the landing URL with wiki-research-web
```

### Semantic Scholar API

```bash
# Search
curl "https://api.semanticscholar.org/graph/v1/paper/search?query=<QUERY>&fields=title,authors,year,abstract,externalIds,openAccessPdf" > /tmp/s2.json

# Fetch by arXiv ID
curl "https://api.semanticscholar.org/graph/v1/paper/arXiv:<ARXIV_ID>?fields=title,authors,year,abstract,citationCount,references" > /tmp/s2_paper.json
```

---

## Step 3 — Write to raw/

Output path: `raw/academic/<year>/<arxiv-id-or-slug>.md`

For non-arXiv papers, use: `raw/academic/<year>/<first-author-last-name>-<short-title>.md`

**Required frontmatter:**
```yaml
---
title: "<Paper Title>"
source_type: academic
source_url: https://arxiv.org/abs/<id>
fetched_date: YYYY-MM-DD
arxiv_id: "2301.12345"       # omit if not arXiv
doi: "10.xxxx/..."            # omit if not known
authors:
  - "First Author"
  - "Second Author"
year: YYYY
venue: "NeurIPS 2024"         # conference/journal if known
abstract: |
  <abstract text>
---

<full paper content or abstract + key sections>
```

---

## Step 4 — Check for related work

For important papers, optionally fetch:
- **Cited-by papers** (if high-impact): Semantic Scholar `citations` endpoint
- **HN discussion** (if notable): search `site:news.ycombinator.com <paper title>` via wiki-research-social
- **Blog post explaining it**: search `<paper title> explained` via wiki-research-web

Limit to 2–3 supplementary sources to avoid scope creep.

---

## Step 5 — Evaluate and return to orchestrator

Run each file through `skills/wiki-research/references/source-eval.md`. Then return to **wiki-research** Step 3 (post-process).

**Wiki citation format:**
```markdown
Chain-of-thought prompting improves multi-step reasoning (Wei et al., 2022 — `raw/academic/2022/wei-chain-of-thought.md`).
```

---

## Done looks like

- Papers or abstracts land under **`raw/academic/`** with structured frontmatter; **source-eval** applied.
- Control returned to **wiki-research** post-process (merge not done inside this skill alone).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| arXiv HTML 404 | Paper predates HTML rendering; use `/abs/` page or fetch PDF with marker adapter |
| arXiv API returns no results | Try broader query; remove category filter |
| DOI redirect loop | Try `https://unpaywall.org/<DOI>` for open-access version |
| Semantic Scholar rate limit (429) | Wait 60s; S2 public API allows ~100 req/5min |
| PDF only (no HTML) | Use `llm-wiki ingest marker <PDF_PATH>` if marker is installed |

---

## Related skills

- **wiki-research** — orchestrator that invoked this skill
- **wiki-research-web** — for non-academic URLs
- **wiki-research-social** — for HN discussions of papers
- **wiki-raw-prepare** — for cleaning PDF/OCR output

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

