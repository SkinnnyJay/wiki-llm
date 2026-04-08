---
name: wiki-extract-paywall
description: Bypass paywalls to get full article text into raw/. Uses Freedium, archive.ph, Wayback Machine, 12ft.io. Auto-invoked on 403/paywall.
user-invocable: false
---

# Wiki extract — paywall bypass

Fetches full article content from paywalled pages using free bypass services. Invoked when a fetch returns a paywall, 403, or subscription prompt. Also usable directly: "bypass paywall for <URL>", "get full article from <URL>".

---

## Quick decision: which service to try first

```
Is it a Medium.com URL (or medium-hosted publication)?
  └─ Yes → Freedium (Priority 1)

Is it any other paywalled URL?
  └─ Try archive.ph first (Priority 2)
  └─ Then Wayback Machine (Priority 3)
  └─ Then RemovePaywall (Priority 4)
  └─ Then 12ft.io (Priority 5)
  └─ Then Googlebot user-agent via Firecrawl (Priority 6)
```

---

## Priority 1 — Freedium (Medium only)

**Best option for Medium articles.** Returns full content directly with no captcha.

Supported domains: `medium.com`, `towardsdatascience.com`, `betterprogramming.pub`, `levelup.gitconnected.com`, `hackernoon.com`, and all custom Medium publications.

```bash
# Transform URL: prepend https://freedium.cfd/
ARTICLE_URL="https://medium.com/@user/some-article-abc123"
BYPASS_URL="https://freedium.cfd/${ARTICLE_URL}"

llm-wiki ingest firecrawl "$BYPASS_URL" \
  --out research/<topic>/<slug>.md

# If Firecrawl unavailable, use stdlib:
llm-wiki ingest url "$BYPASS_URL" \
  --out research/<topic>/<slug>.md
```

If Freedium returns a 429 (rate limit), wait 30s and retry once. If it still fails, fall through to archive.ph.

---

## Priority 2 — Archive.ph / Archive.today

Works for most major news sites (NYT, WSJ, FT, Bloomberg, The Atlantic, etc.).

```bash
ARTICLE_URL="https://example.com/paywalled-article"

# Check if already archived:
llm-wiki ingest url "https://archive.ph/${ARTICLE_URL}" \
  --out research/<topic>/<slug>.md

# If not archived yet, request a new snapshot (opens browser-side — inform user):
# https://archive.ph/?run=1&url=<ARTICLE_URL>
```

Archive.ph may require a CAPTCHA for new snapshot requests. If so, tell the user and try Wayback Machine instead.

---

## Priority 3 — Wayback Machine

Good fallback for archived articles. May not have the very latest version.

```bash
# Fetch most recent archive snapshot
ARTICLE_URL="https://example.com/paywalled-article"

# Find available snapshots:
llm-wiki ingest url "https://archive.org/wayback/available?url=${ARTICLE_URL}" \
  --out /tmp/wayback-check.json
# Parse the JSON to get the closest snapshot URL

# Then fetch the snapshot:
llm-wiki ingest firecrawl "https://web.archive.org/web/*/${ARTICLE_URL}" \
  --out research/<topic>/<slug>.md
```

---

## Priority 4 — RemovePaywall

Aggregates multiple bypass methods. Simple redirect-based.

```bash
ARTICLE_URL="https://example.com/paywalled-article"
llm-wiki ingest firecrawl "https://www.removepaywall.com/search?url=${ARTICLE_URL}" \
  --out research/<topic>/<slug>.md
```

Note: RemovePaywall may return a redirect page rather than the full content. If the fetched output is just a list of buttons/links rather than article text, fall through to the next method.

---

## Priority 5 — 12ft.io

Works by showing Google's cached version. Good for sites with soft paywalls.

```bash
ARTICLE_URL="https://example.com/paywalled-article"
llm-wiki ingest firecrawl "https://12ft.io/${ARTICLE_URL}" \
  --out research/<topic>/<slug>.md
```

12ft.io has been intermittently blocked by some publishers. If it fails, use Googlebot spoofing.

---

## Priority 6 — Googlebot user-agent spoofing (Firecrawl only)

Many sites with soft paywalls show full content to Googlebot since they want Google to index their articles. Requires Firecrawl.

```bash
# Firecrawl supports custom headers
llm-wiki ingest firecrawl "<ARTICLE_URL>" \
  --header "User-Agent: Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)" \
  --out research/<topic>/<slug>.md
```

If `llm-wiki ingest firecrawl` does not support `--header`, use the Firecrawl REST API directly:
```bash
curl -X POST "https://api.firecrawl.dev/v1/scrape" \
  -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"<ARTICLE_URL>\", \"headers\": {\"User-Agent\": \"Googlebot\"}}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['markdown'])" \
  > raw/research/<topic>/<slug>.md
```

---

## Priority 7 — Disable JavaScript (stdlib fallback)

Some paywalls are injected by JavaScript. Fetching without JS execution may return the raw content.

```bash
# stdlib url adapter never runs JS — it's already a no-JS fetch
llm-wiki ingest url "<ARTICLE_URL>" \
  --out research/<topic>/<slug>.md
```

If this returns the full article body (check for > 500 words of actual text), it worked. If it returns a stub or paywall message, the site uses a hard paywall (content never sent to client without subscription) — no bypass possible.

---

## Hard paywalls (cannot be bypassed)

Hard paywalls load article content only after server-side auth check — no archived copy, no bypass will work. Recognizable because:
- All bypass services return the same empty/stub content
- The page body has < 200 words
- JS is required to load content AND the site requires auth before serving JS

**When you hit a hard paywall:**
1. Note it in frontmatter: `paywall: hard`
2. Fetch only the article title, summary (if in `<meta>` tags), and publication date
3. Log in `wiki/log.md`: `[PAYWALLED] <URL> — hard paywall, partial metadata only`
4. Consider fetching from Anna's Archive if it's a book/paper — invoke **wiki-extract-annas**

---

## Frontmatter to add

```yaml
---
source_url: https://...           # original paywalled URL
bypass_method: freedium | archive.ph | wayback | removepaywall | 12ft | googlebot | stdlib
bypass_url: https://...           # URL actually fetched
fetched_date: YYYY-MM-DD
paywall: soft | hard | none       # result
source_type: web
---
```

---

## After bypass — return to caller

If invoked from **wiki-research-web**: return to that skill's Step 5 (evaluate) with the bypassed file.
If invoked directly: proceed to **wiki-research** Step 3 (post-process) — validate, ingest, log.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Freedium 429 | Wait 30s; Freedium has rate limits |
| archive.ph returns "Saving in progress" | Wait 60–120s for new snapshot; retry URL |
| 12ft.io returns blank page | Site has hard paywall or blocked 12ft; try Googlebot spoof |
| RemovePaywall returns button page only | Use Firecrawl on the redirected URL it points to |
| Googlebot header rejected | Site checks Googlebot IP too; no bypass possible |
| All methods return < 200 words | Hard paywall; note `paywall: hard` and log |

---

## Done looks like

- **`raw/`** file contains best-effort article text; frontmatter records **`bypass_method`** and **`paywall`** result.
- **`wiki/log.md`** notes hard paywalls when only metadata was recoverable.

## Related skills

- **wiki-research-web** — primary web fetch skill that invokes this on paywall detection
- **wiki-extract-annas** — fetch books/papers from Anna's Archive as alternative to paywalled content
- **wiki-extract-ebook** — extract text from downloaded EPUB/PDF files

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

