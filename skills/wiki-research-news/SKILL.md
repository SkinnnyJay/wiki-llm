---
name: wiki-research-news
description: Research current events using Perplexity or news APIs and ingest into raw/news/. Invoked by wiki-research for recency-first queries.
user-invocable: false
---

# Wiki research — news

Fetches current-events content using Perplexity (primary) or news aggregators via Firecrawl (fallback) into `raw/news/`. Use this sub-skill when the user wants recent or time-sensitive information: "what happened with X", "latest news on Y", "this week in Z".

---

## Step 1 — Check adapter availability

**Priority 0 — Read the config first:**
```bash
llm-wiki integrations status
```

Open `llm-wiki/config.json` → `integrations` and build the enabled list. Only consider adapters where **`enabled: true`** AND their `api_key_env` is set in the environment.

Then use the first ready and enabled adapter:

| Priority | Adapter | Config key | Condition |
|----------|---------|------------|-----------|
| 0 | **config check** | — | Read `llm-wiki/config.json`; build enabled list |
| 1 | **Perplexity** | `integrations.perplexity` | `enabled: true` + `PERPLEXITY_API_KEY` set |
| 2 | **Brave Search** | `integrations.brave` | `enabled: true` + `BRAVE_SEARCH_API_KEY` set — good for news in `news` mode |
| 3 | **NewsAPI** | — | `NEWS_API_KEY` set (not in default config; add if needed) |
| 4 | **Firecrawl on news sites** | `integrations.firecrawl` | `enabled: true` + Firecrawl CLI or REST available |
| 5 | **stdlib on plain-text news** | — | Always available (limited) |

---

## Step 2 — Construct the query

See `skills/wiki-research/references/query-design.md` — News section.

**For Perplexity:**
- Include the current year/month for recency grounding.
- Use declarative prompts, not open-ended questions.
- Request citations: "Include source URLs."

Example queries:
```
"AI regulation developments April 2026. Include source URLs."
"What happened with OpenAI in the past 7 days? Include citations."
"Summarize the latest research on LLM reasoning. Focus on papers published in 2026."
```

---

## Step 3 — Fetch via Perplexity (primary)

```bash
llm-wiki ingest perplexity "<query>" \
  --out news/<YYYY-MM-DD>/<topic-slug>.md
```

The Perplexity adapter will include cited URLs in the output. After ingesting:
1. Extract cited URLs from the Perplexity output.
2. Optionally fetch 1–3 of the most relevant cited pages via **wiki-research-web** for deeper raw evidence.

---

## Step 4 — Fetch via Brave Search (fallback)

If Perplexity is unavailable but `integrations.brave` is `enabled: true` and `BRAVE_SEARCH_API_KEY` is set:

```bash
# Brave news mode — returns structured recent articles
llm-wiki ingest brave "<query>" --mode news \
  --out news/<YYYY-MM-DD>/<topic-slug>-brave.md

# Or llm-context mode for a pre-synthesized answer with citations
llm-wiki ingest brave "<query>" --mode llm-context \
  --out news/<YYYY-MM-DD>/<topic-slug>-brave.md
```

After ingesting: extract article URLs from Brave results and optionally fetch 1–3 full articles via **wiki-research-web**.

---

## Step 5 — Fetch via NewsAPI (fallback)

If Perplexity and Brave are unavailable and `NEWS_API_KEY` is set:

```bash
# Top headlines for a topic
curl "https://newsapi.org/v2/everything?q=<QUERY>&sortBy=publishedAt&pageSize=10&apiKey=$NEWS_API_KEY" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
for a in data.get('articles', []):
    print(a['publishedAt'][:10], a['url'], a['title'])
"
# Then fetch each article URL via wiki-research-web
```

---

## Step 6 — Fetch via Firecrawl on news aggregators (last fallback)

If none of the above are available:

```bash
# Google News (requires Firecrawl for JS rendering)
llm-wiki ingest firecrawl "https://news.google.com/search?q=<QUERY>&hl=en" \
  --out news/<YYYY-MM-DD>/<topic-slug>-goog.md

# Hacker News search (no JS needed)
llm-wiki ingest url "https://hn.algolia.com/api/v1/search?query=<QUERY>&tags=story&hitsPerPage=10" \
  --out news/<YYYY-MM-DD>/<topic-slug>-hn.md

# TechCrunch / The Verge (JS rendering needed)
llm-wiki ingest firecrawl "https://techcrunch.com/?s=<QUERY>" \
  --out news/<YYYY-MM-DD>/<topic-slug>-tc.md
```

---

## Step 7 — Write frontmatter

```yaml
---
source_type: news
source_url: https://...       # Perplexity result URL or aggregator URL
query: "<query used>"
fetched_date: YYYY-MM-DD
published_date: YYYY-MM-DD    # of the news item, if known
adapter: perplexity | brave | newsapi | firecrawl | stdlib_url
topics: [<tags>]
---
```

For Perplexity outputs, set `source_url` to the Perplexity canonical URL if available, or leave as `perplexity-query`.

---

## Step 8 — Evaluate and return to orchestrator

News sources typically score high on recency but variable on authority. Check:
- Is the source a recognized outlet (tier 2) or unknown (tier 4–5)?
- Is the content actual reporting or clickbait/speculation?

Run through `skills/wiki-research/references/source-eval.md`.

Then return to **wiki-research** Step 3 (post-process).

---

## Done looks like

- At least one **`raw/news/`** (or agreed) file with query + date metadata; best available adapter used per config.
- **source-eval** applied; orchestrator handles merge.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `PERPLEXITY_API_KEY` missing | `export PERPLEXITY_API_KEY=pplx-...` or `llm-wiki integrations wizard` |
| Perplexity rate limit (429) | Wait 60s; Perplexity free tier is limited |
| Perplexity returns outdated info | Add current year to query; Perplexity may have knowledge cutoff |
| `BRAVE_SEARCH_API_KEY` missing | `export BRAVE_SEARCH_API_KEY=...` or `llm-wiki integrations wizard` |
| Brave returns no news results | Switch `--mode news` to `--mode web` or try Perplexity |
| NewsAPI returns paywalled articles | Fetch abstract only; note `[PAYWALLED]` in frontmatter |
| Google News returns empty via Firecrawl | Try adding `&gl=US&ceid=US:en` to URL |
| All adapters unavailable | Run `llm-wiki integrations wizard` to configure Perplexity or Brave |

---

## Related skills

- **wiki-research** — orchestrator that invoked this skill
- **wiki-research-web** — for fetching full articles discovered in news results
- **wiki-research-academic** — for citing papers referenced in news coverage
- **wiki-research-social** — for HN/Twitter discussion of news items

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

