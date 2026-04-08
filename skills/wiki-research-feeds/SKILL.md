---
name: wiki-research-feeds
description: Monitor RSS/Atom feeds or OPML lists and ingest recent items into raw/feeds/. Invoked by wiki-research for feed/newsletter research.
user-invocable: false
---

# Wiki research — feeds

Fetches items from RSS/Atom feeds or OPML lists into `raw/feeds/`. Use this sub-skill when the input is a feed URL, OPML file, or the user wants to monitor a set of sources for recent content.

---

## Step 1 — Determine input format

| Input | Action |
|-------|--------|
| Single feed URL (`.xml`, `.rss`, `/feed`, `/atom`) | Fetch and parse directly |
| OPML file path | Parse OPML to extract all feed URLs, then process each |
| Blog URL (not feed URL) | Auto-discover feed: try `<URL>/feed`, `<URL>/rss`, `<URL>/atom.xml` |
| Comma-separated list of URLs | Process each as individual feeds |

---

## Step 2 — Check adapter availability

**Preferred: `feed` CLI**
```bash
which feed && feed --version
```

If available:
```bash
feed fetch <FEED_URL> --since 24h --format json > /tmp/feed-items.json
```

**Fallback: stdlib XML parsing**
```bash
llm-wiki ingest url <FEED_URL> --out feeds/raw/<source-slug>.xml
# Then parse with Python:
python3 << 'EOF'
import xml.etree.ElementTree as ET, json, sys
tree = ET.parse('feeds/raw/<source-slug>.xml')
root = tree.getroot()
ns = {'atom': 'http://www.w3.org/2005/Atom'}
# Handle both RSS 2.0 and Atom
items = root.findall('.//item') or root.findall('.//atom:entry', ns)
for item in items:
    title = item.findtext('title') or item.findtext('atom:title', namespaces=ns)
    link = item.findtext('link') or item.findtext('atom:link', namespaces=ns)
    pubdate = item.findtext('pubDate') or item.findtext('atom:updated', namespaces=ns)
    print(json.dumps({'title': title, 'link': link, 'date': pubdate}))
EOF
```

---

## Step 3 — Apply recency filter

Only process items published within the recency window. Default: **last 7 days**.

For monitoring / daily digests: use **last 24 hours**.

```bash
# With feed CLI
feed fetch <URL> --since 24h

# Manual date check (Python)
from datetime import datetime, timedelta, timezone
cutoff = datetime.now(timezone.utc) - timedelta(days=7)
# Skip items where parsed_date < cutoff
```

---

## Step 4 — Deduplicate against existing raw/

Before fetching each item's full content:
```bash
llm-wiki raw rebuild-index
# Then check:
grep -r "source_url: <ITEM_URL>" raw/feeds/
```

Skip items already present in `raw/` (same URL).

---

## Step 5 — Fetch full content for each item

For each new item that passes the recency and dedup filters:

```bash
llm-wiki ingest firecrawl "<ITEM_URL>" \
  --out feeds/<source-slug>/<YYYY-MM-DD>/<item-slug>.md
```

If Firecrawl is unavailable, use stdlib:
```bash
llm-wiki ingest url "<ITEM_URL>" \
  --out feeds/<source-slug>/<YYYY-MM-DD>/<item-slug>.md
```

**Limit:** Cap at **20 items per feed per run** to avoid context overflow.

---

## Step 6 — OPML processing

If input is an OPML file:
```python
import xml.etree.ElementTree as ET
tree = ET.parse('<OPML_PATH>')
feeds = [el.get('xmlUrl') for el in tree.findall('.//outline[@xmlUrl]')]
# feeds is now a list of RSS/Atom URLs — process each with Steps 2–5
```

Process feeds sequentially; do not parallelize (respect rate limits).

---

## Step 7 — Add frontmatter to each file

```yaml
---
source_type: feed
feed_url: https://...
feed_title: "Example Blog"
source_url: https://...          # item link
item_title: "<article title>"
item_published: YYYY-MM-DD
fetched_date: YYYY-MM-DD
adapter: firecrawl | stdlib_url
---
```

---

## Step 8 — Evaluate and return to orchestrator

Run each file through `skills/wiki-research/references/source-eval.md`. Feed items often need recency evaluation — skip low-relevance items rather than ingesting everything.

Write a **digest summary** if requested:
- Summarize all ingested items in `outputs/feeds-digest-<YYYY-MM-DD>.md`
- List: title, source, 1-sentence summary, path to raw file

Then return to **wiki-research** Step 3 (post-process).

---

## Done looks like

- Feed items ingested under **`raw/feeds/`** with frontmatter; recency/dedup rules applied.
- Optional digest written under **`outputs/`** when requested.
- Orchestrator handles post-process and **wiki-ingest**.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Feed URL returns HTML not XML | Site requires JS; try `<URL>/feed.xml` or check site for feed link in `<head>` |
| feed CLI not found | `pip install feed-cli` or use Python stdlib XML fallback |
| 429 from feed server | Wait 60s; some servers throttle XML requests |
| OPML has outdated/dead feed URLs | Skip 404s; note `[DEAD]` in OPML review |
| Items have no full content (abstract only) | Fetch linked article URL via wiki-research-web |

---

## Related skills

- **wiki-research** — orchestrator that invoked this skill
- **wiki-research-web** — for fetching full article content from feed item links
- **wiki-research-news** — for general news queries (not feed-based monitoring)
- **wiki-research-loop** — for recurring batch monitoring with research-tasks.json

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

