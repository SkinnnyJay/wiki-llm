---
name: wiki-extract-newsletter
description: Extract Substack, Beehiiv, Ghost, Buttondown newsletter issues into raw/. Handles subscriber-only content via archives, RSS, and email.
disable-model-invocation: true
argument-hint: "<newsletter URL or publication name>"
---

# Wiki extract — newsletter

Extracts newsletter issues from Substack, Beehiiv, Ghost, Buttondown, and similar platforms into `raw/` for wiki ingestion. Use when:
- The user shares a newsletter issue URL or publication homepage.
- A newsletter publication needs to be tracked in the vault.
- "Get this Substack post", "archive this newsletter", "add this issue to the wiki".
- Content is behind a subscriber paywall that `wiki-extract-paywall` doesn't handle well.

This skill handles newsletter-specific patterns: archive pages, RSS feeds, subscriber paywalls, and email-forwarded HTML.

---

## Step 1 — Identify the platform and URL type

| URL pattern | Platform | Strategy |
|-------------|----------|----------|
| `<pub>.substack.com/p/<slug>` | Substack | Fetch directly; paid posts need Step 3 |
| `substack.com/@<user>/p/<slug>` | Substack | Same |
| `<pub>.beehiiv.com/p/<slug>` | Beehiiv | Direct fetch via Firecrawl |
| `<domain>.ghost.io/...` or self-hosted Ghost | Ghost | Direct fetch or Ghost Content API |
| `buttondown.email/<name>/archive/<slug>` | Buttondown | Direct fetch (all public) |
| `<pub>.mailchimp.com/...` | Mailchimp | Archive page fetch |
| Raw email HTML file (`.eml` or `.html`) | Any | Parse locally (Step 5) |

---

## Step 2 — Check adapter availability

```bash
llm-wiki integrations status
```

Newsletter platforms are mostly server-rendered, so stdlib often works. Firecrawl is preferred for paywalled Substack and Beehiiv issues.

---

## Step 3 — Substack

### Free / public post

```bash
POST_URL="https://<pub>.substack.com/p/<slug>"
SLUG="<pub>-<slug>"
OUT_DIR="raw/newsletters/${SLUG}"
mkdir -p "$OUT_DIR"

llm-wiki ingest firecrawl "$POST_URL" --out "${OUT_DIR}/issue.md"
# Fallback:
llm-wiki ingest url "$POST_URL" --out "${OUT_DIR}/issue.md"
```

### Paid / subscriber-only post

Substack paid posts load content only after client-side auth — no bypass service reliably works. Try in order:

**Option A — archive.ph** (often has subscriber-shared snapshots):
```bash
llm-wiki ingest firecrawl "https://archive.ph/${POST_URL}" \
  --out "${OUT_DIR}/issue.md"
```

**Option B — Substack RSS feed** (free posts only, but worth checking):
```bash
PUB="<pub>"
llm-wiki ingest url "https://${PUB}.substack.com/feed" \
  --out "${OUT_DIR}/feed.xml"
# Parse feed for post content; paid posts appear as stubs with preview only
```

**Option C — Reader mode via 12ft.io** (soft paywalls only):
```bash
llm-wiki ingest firecrawl "https://12ft.io/${POST_URL}" \
  --out "${OUT_DIR}/issue.md"
```

**Option D — If user has subscriber access**: ask them to forward the email HTML (see Step 5).

If all bypass methods return < 300 words of article text, note `paywall: hard` in frontmatter.

### Substack publication archive

```bash
PUB="<pub>"

# Archive page (shows all public posts with titles/dates)
llm-wiki ingest firecrawl "https://${PUB}.substack.com/archive" \
  --out "raw/newsletters/${PUB}/archive.md"

# RSS feed for recent issues
llm-wiki ingest url "https://${PUB}.substack.com/feed" \
  --out "raw/newsletters/${PUB}/feed.xml"
```

---

## Step 4 — Beehiiv

Beehiiv newsletters are usually fully public in their archive:

```bash
PUB="<pub>"
SLUG="<post-slug>"
OUT_DIR="raw/newsletters/${PUB}"
mkdir -p "$OUT_DIR"

# Single post
llm-wiki ingest firecrawl "https://www.beehiiv.com/p/${SLUG}" \
  --out "${OUT_DIR}/${SLUG}.md"

# Or via custom domain
llm-wiki ingest firecrawl "https://${PUB}.beehiiv.com/p/${SLUG}" \
  --out "${OUT_DIR}/${SLUG}.md"
```

Beehiiv RSS:
```bash
llm-wiki ingest url "https://${PUB}.beehiiv.com/feed.xml" \
  --out "${OUT_DIR}/feed.xml"
```

---

## Step 5 — Ghost

### Via Ghost Content API (preferred for self-hosted or Ghost Pro)

```bash
# Requires: GHOST_CONTENT_API_KEY and GHOST_URL from vault config or user
GHOST_URL="https://<domain>"
GHOST_KEY="${GHOST_CONTENT_API_KEY}"

# Fetch single post by slug
curl -s "${GHOST_URL}/ghost/api/content/posts/slug/<slug>/?key=${GHOST_KEY}&formats=markdown" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
post = data['posts'][0]
print(f\"# {post['title']}\n\n{post.get('markdown', post.get('html',''))}\")
" > "${OUT_DIR}/post.md"

# Fetch all posts
curl -s "${GHOST_URL}/ghost/api/content/posts/?key=${GHOST_KEY}&limit=all&formats=markdown" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
for p in data['posts']:
    print(f\"{p['published_at'][:10]} {p['slug']}: {p['title']}\")
"
```

### Via direct fetch (public Ghost site)

```bash
llm-wiki ingest firecrawl "${GHOST_URL}/<slug>/" --out "${OUT_DIR}/post.md"
```

---

## Step 6 — Parse email HTML (forwarded newsletter)

When the user has a subscriber copy and forwards the `.eml` file or HTML:

```bash
# Save the .eml or .html to raw/newsletters/<pub>/
EMAIL_FILE="raw/newsletters/<pub>/issue-<date>.eml"

python3 << 'PYEOF'
import email, sys, pathlib, re
from html.parser import HTMLParser

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self._skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ('style', 'script'): self._skip = True
    def handle_endtag(self, tag):
        if tag in ('style', 'script'): self._skip = False
    def handle_data(self, data):
        if not self._skip and data.strip():
            self.text.append(data.strip())

msg = email.message_from_string(pathlib.Path(sys.argv[1]).read_text(errors='replace'))
subject = msg['subject'] or 'Unknown Subject'
sender  = msg['from']   or 'Unknown Sender'
date    = msg['date']   or 'Unknown Date'

html_body = ''
for part in msg.walk():
    if part.get_content_type() == 'text/html':
        html_body = part.get_payload(decode=True).decode('utf-8', errors='replace')
        break
    elif part.get_content_type() == 'text/plain' and not html_body:
        html_body = part.get_payload(decode=True).decode('utf-8', errors='replace')

ext = TextExtractor()
ext.feed(html_body)
body = '\n'.join(ext.text)

print(f"# {subject}\n\n**From:** {sender}  \n**Date:** {date}\n\n{body}")
PYEOF
python3 -c "..." "$EMAIL_FILE" > "${OUT_DIR}/issue-<date>.md"
```

---

## Step 7 — Write to raw/ with frontmatter

Output path: `raw/newsletters/<publication>/<YYYY-MM-DD>-<slug>.md`

```yaml
---
title: "<Issue Title>"
publication: "<Publication Name>"
author: "<Author>"
source_url: https://...
source_type: newsletter
platform: substack | beehiiv | ghost | buttondown | mailchimp | email
pub_date: YYYY-MM-DD
issue_number: <N>             # if known
paywall: none | soft | hard
bypass_method: direct | archive.ph | rss | 12ft | email_forward
fetched_date: YYYY-MM-DD
---
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Substack post returns preview only | Paid post; try archive.ph, then ask user to forward email |
| `archive.ph` returns "Saving in progress" | Wait 60–120s; retry |
| Beehiiv post is empty | Check the correct subdomain; try `beehiiv.com/p/<slug>` vs `<pub>.beehiiv.com/p/<slug>` |
| Ghost Content API returns 401 | Key is wrong or expired; regenerate at `<domain>/ghost/#/settings/integrations` |
| Email HTML produces garbled text | Run through **wiki-raw-prepare** to clean markdown |
| RSS feed only shows excerpts | Platform restricts full content in feed; use direct fetch or email forward |

---

## Done looks like

- Full issue or best-available excerpt in **`raw/`** with platform + issue metadata; subscriber-only gaps explicit.

## Related skills

- **wiki-research-feeds** — for following newsletters as RSS feeds (headlines + excerpts only)
- **wiki-extract-paywall** — for general paywall bypass; this skill handles newsletter-specific patterns first
- **wiki-research-web** — for general web article fetch when the newsletter links to external articles
- **wiki-raw-prepare** — clean and restructure newsletter markdown before wiki ingestion

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

