---
name: wiki-research-social
description: Fetch Twitter/X threads, Hacker News discussions, or Reddit posts into raw/social/. Invoked by wiki-research for social/community content.
user-invocable: false
---

# Wiki research — social

Fetches social and community content (Twitter/X, Hacker News, Reddit) into `raw/social/`. Use this sub-skill when the input is a social URL or the user wants community discussion around a topic.

---

## Step 1 — Identify the platform

| Input signal | Platform | Command |
|-------------|----------|---------|
| `x.com`, `twitter.com` URL or "tweet"/"thread" | Twitter/X | `llm-wiki ingest twitter` |
| `news.ycombinator.com` URL, HN item ID, "HN thread", "Show HN" | Hacker News | `llm-wiki ingest hackernews` |
| `reddit.com` URL, "subreddit", "Reddit post" | Reddit | Firecrawl on `old.reddit.com` |
| Keyword search ("what are people saying about X") | Multiple | Run HN search + Twitter search |

---

## Step 2 — Twitter/X

**Single tweet (zero-config, public):**
```bash
llm-wiki ingest twitter https://x.com/<user>/status/<id> \
  --out social/twitter/<YYYY-MM-DD>/<user>-<id>.md
```

**Full thread (requires bird CLI):**
```bash
llm-wiki ingest twitter https://x.com/<user>/status/<id> --thread \
  --out social/twitter/<YYYY-MM-DD>/<user>-thread-<id>.md
```

**Keyword search (requires bird CLI + `TWITTER_AUTH_TOKEN`):**
```bash
llm-wiki ingest twitter --search "<query>" --limit 20 \
  --out social/twitter/<YYYY-MM-DD>/search-<slug>.md
# Good query patterns:
# "AI agents" lang:en -is:retweet since:2026-01-01
# from:<handle> filter:links
```

**User timeline (requires bird CLI + `TWITTER_AUTH_TOKEN`):**
```bash
llm-wiki ingest twitter --user @<handle> --limit 50 \
  --out social/twitter/<YYYY-MM-DD>/<handle>-timeline.md
```

**Required frontmatter:**
```yaml
source_type: social
platform: twitter
post_id: "<tweet-id>"
author: "@handle"
posted_date: YYYY-MM-DD
thread: true | false
```

---

## Step 3 — Hacker News

**Thread by URL:**
```bash
llm-wiki ingest hackernews https://news.ycombinator.com/item?id=<ID> \
  --out social/hn/<YYYY-MM-DD>/<id>-<slug>.md
```

**Thread by item ID:**
```bash
llm-wiki ingest hackernews <ID> \
  --out social/hn/<YYYY-MM-DD>/<id>.md
```

**Search for HN threads on a topic (Algolia API):**
```bash
curl "https://hn.algolia.com/api/v1/search?query=<QUERY>&tags=story&hitsPerPage=5" \
  | python3 -c "import json,sys; [print(h['url'],h['objectID']) for h in json.load(sys.stdin)['hits']]"
# Then fetch each thread ID individually
```

**Required frontmatter:**
```yaml
source_type: social
platform: hackernews
post_id: "<hn-item-id>"
hn_url: https://news.ycombinator.com/item?id=<id>
posted_date: YYYY-MM-DD
score: <points>           # if available
```

See `skills/wiki-research-loop/references/hn-example.md` for HN API ethics and rate limits.

---

## Step 4 — Reddit

Reddit does not require an API key for public posts via `old.reddit.com`.

**Single post with comments:**
```bash
# Plain-text JSON (no auth needed)
curl "https://old.reddit.com/r/<subreddit>/comments/<id>/<slug>.json?limit=100" \
  -H "User-Agent: wiki-llm-research/1.0" \
  -o /tmp/reddit-<id>.json

# Or fetch readable HTML via Firecrawl:
llm-wiki ingest firecrawl "https://old.reddit.com/r/<subreddit>/comments/<id>/<slug>/" \
  --out social/reddit/<YYYY-MM-DD>/r-<subreddit>-<id>.md
```

**Top posts from a subreddit:**
```bash
curl "https://old.reddit.com/r/<subreddit>/top.json?t=week&limit=10" \
  -H "User-Agent: wiki-llm-research/1.0" | python3 -c \
  "import json,sys; [print(p['data']['url']) for p in json.load(sys.stdin)['data']['children']]"
```

**Required frontmatter:**
```yaml
source_type: social
platform: reddit
subreddit: "<name>"
post_id: "<reddit-id>"
reddit_url: https://old.reddit.com/r/<subreddit>/comments/<id>/
posted_date: YYYY-MM-DD
```

---

## Step 5 — Deduplication

Before writing each file, check for existing ingests of the same post:

```bash
grep -r "post_id: \"<id>\"" raw/social/
```

If found and the existing file is recent, skip and log `[SKIP] duplicate: raw/social/...`.

---

## Step 6 — Evaluate and return to orchestrator

Run each file through `skills/wiki-research/references/source-eval.md`. Social content often scores lower on authority (tier 3) — this is expected; adjust expectations accordingly.

Then return to **wiki-research** Step 3 (post-process).

---

## Done looks like

- Platform identified; content under **`raw/social/`** (or agreed path); dedup applied.
- **source-eval** run; orchestrator post-process handles **wiki-ingest**.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| fxTwitter returns empty | Tweet may be deleted; try Wayback Machine |
| bird CLI not found | `npm install -g bird-cli` or use `llm-wiki integrations wizard` |
| `TWITTER_AUTH_TOKEN` missing | Sign in to X, copy auth token from browser devtools (Application → Cookies) |
| HN item 404 | Check item ID; item may have been flagged/deleted |
| Reddit 429 | Add `User-Agent` header; wait 10s between requests |
| Reddit post is [removed] | Note as `[REMOVED]` in frontmatter; do not ingest placeholder text |

---

## Related skills

- **wiki-research** — orchestrator that invoked this skill
- **wiki-research-web** — for general URLs discovered in social posts
- **wiki-research-academic** — for papers linked in social threads
- **wiki-research-loop** — batch HN/social monitoring via research-tasks.json

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

