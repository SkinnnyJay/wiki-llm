# Query Design — Per-Modality Construction Guide

Use this reference when you need to turn a vague user request into a precise, executable query for each research modality.

---

## General Principles

1. **Be specific first** — narrow queries return cleaner results. You can always broaden.
2. **Use modality-native syntax** — each system (arXiv, HN, Perplexity, etc.) has its own query language.
3. **Record the query** — write it in the raw file's frontmatter under `search_query:` for reproducibility.
4. **Limit scope** — cap results at a reasonable number (10–25) per run; more is not better.

---

## Web (wiki-research-web)

**Input form:** One or more URLs.

- Prefer direct article URLs over search-result pages.
- If you only have a topic, use Perplexity (`wiki-research-news`) or Brave Search, or an arXiv search (`wiki-research-academic`) to discover the canonical URL first.
- For JS-rendered sites, Firecrawl is required — stdlib `url` adapter will return empty body.
- Check `llm-wiki/config.json` integrations before picking an adapter — only use adapters with `enabled: true`.
- Filename slug: lowercase, hyphens, no query params. E.g. `hn-43012345.md` or `blog-post-title.md`.

```yaml
# frontmatter to add
source_url: https://...
fetched_date: YYYY-MM-DD
adapter: brave | firecrawl | firecrawl_rest | stdlib_url
```

---

## Academic (wiki-research-academic)

**arXiv API query syntax:**
```
https://export.arxiv.org/api/query?search_query=<QUERY>&max_results=10&sortBy=relevance
```

Query fields:
- `ti:` — title
- `au:` — author
- `abs:` — abstract
- `cat:` — category (e.g. `cs.AI`, `cs.LG`, `q-bio.NC`)
- `all:` — all fields

Examples:
```
all:retrieval-augmented generation+AND+cat:cs.AI
ti:chain-of-thought+AND+au:wei
```

**DOI resolution:** `https://doi.org/<DOI>` — follow redirect to get landing page URL, then fetch with wiki-research-web.

**Semantic Scholar:**
```
https://api.semanticscholar.org/graph/v1/paper/search?query=<QUERY>&fields=title,authors,year,abstract,externalIds
```

**Frontmatter to add:**
```yaml
source_type: academic
arxiv_id: "2301.12345"       # if arXiv
doi: "10.xxxx/xxx"            # if DOI known
authors: [Name, Name]
year: YYYY
venue: NeurIPS 2024
```

---

## Social (wiki-research-social)

**Twitter/X — single tweet (zero-config):**
```bash
llm-wiki ingest twitter https://x.com/<user>/status/<id>
```

**Twitter/X — thread (requires bird CLI):**
```bash
llm-wiki ingest twitter https://x.com/<user>/status/<id> --thread
```

**Twitter/X — keyword search (requires bird CLI + `TWITTER_AUTH_TOKEN`):**
```bash
llm-wiki ingest twitter --search "<keywords>" --limit 20
# Good search patterns:
# "AI agents" lang:en -is:retweet since:2026-01-01
# from:karpathy deep learning
```

**HN — thread by URL or item ID:**
```bash
llm-wiki ingest hackernews https://news.ycombinator.com/item?id=<ID>
# Or just the ID:
llm-wiki ingest hackernews <ID>
```

**HN — search (Algolia):**
```
https://hn.algolia.com/api/v1/search?query=<QUERY>&tags=story&hitsPerPage=10
```
Fetch the resulting story URLs individually.

**Reddit — plain text (no API needed):**
```
https://old.reddit.com/r/<subreddit>/comments/<id>/<slug>/.json
```
Fetch with stdlib url adapter; strip `.json` suffix for human-readable HTML via Firecrawl.

**Frontmatter to add:**
```yaml
source_type: social
platform: twitter | hackernews | reddit
post_id: "<id>"
author: "@handle"
posted_date: YYYY-MM-DD
```

---

## Feeds (wiki-research-feeds)

**Input:** OPML file path or list of feed URLs.

**Using the `feed` CLI (if installed):**
```bash
feed fetch <URL> --since 24h --format json
```

**Stdlib XML fallback:**
```bash
llm-wiki ingest url <FEED_URL> --out feeds/<source>/raw.xml
# Then parse frontmatter manually or with:
python3 -c "import xml.etree.ElementTree as ET; ..."
```

**Filter strategy:**
- Always apply a recency window: prefer last 24h–7d.
- Skip items whose `<link>` is already in `raw/` (check `llm-wiki raw rebuild-index`).

**Frontmatter to add:**
```yaml
source_type: feed
feed_url: https://...
feed_title: "Example Blog"
item_published: YYYY-MM-DD
```

---

## News (wiki-research-news)

**Perplexity (primary — requires `PERPLEXITY_API_KEY`):**
```bash
llm-wiki ingest perplexity "<research question or news topic>"
# Example: "AI regulation updates April 2026"
```

Good query patterns for Perplexity:
- Append current year/month for recency: `"topic" April 2026`
- Ask for sources explicitly: `"Summarize recent papers on X. Include citations."`
- Avoid open-ended questions; prefer declarative prompts.

**Fallback — Firecrawl on news aggregators:**
```bash
llm-wiki ingest firecrawl "https://news.google.com/search?q=<topic>&hl=en"
llm-wiki ingest firecrawl "https://techcrunch.com/search/<topic>/"
```

**Frontmatter to add:**
```yaml
source_type: news
published_date: YYYY-MM-DD
query: "<perplexity or search query used>"
```

---

## Deep Research (wiki-research-deep)

Deep research has no single query — it composes multiple modality queries.

**Planning the query set:**
1. Write a 1-sentence research question.
2. Decompose into 3–5 sub-questions, each answerable by one modality.
3. Map each sub-question to a sub-skill.
4. Run sub-skills in dependency order (academic → web → social/news).

**Intermediate synthesis prompt (for `outputs/` draft):**
```
Given these sources: [list raw/ paths]
Synthesize a comprehensive answer to: [research question]
Include: key findings, contradictions, open questions, citations.
Aim for 500–1500 words.
```

See `synthesis.md` for the full merge workflow.
