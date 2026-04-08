---
name: wiki-extract-linkedin
description: Extract LinkedIn profiles, jobs, and posts into raw/. Uses Firecrawl, archive.ph, Google cache, or manual export bypass hierarchy.
disable-model-invocation: true
argument-hint: "<LinkedIn URL>"
---

# Wiki extract — LinkedIn

Extracts public content from LinkedIn company pages, job listings, and posts into `raw/` for wiki ingestion. Use when:
- Researching a company's public profile, team size, or recent posts.
- Capturing job listing data for market research.
- "Get LinkedIn data for company X", "what does Y's LinkedIn say?", "capture this job listing".

**Warning:** LinkedIn is the most aggressively bot-blocked platform in this skill suite. Expect higher failure rates than other platforms. This skill documents the full bypass hierarchy — most failures are recoverable.

---

## Step 1 — Identify the URL type

| URL pattern | Content |
|-------------|---------|
| `linkedin.com/company/<slug>` | Company overview (employees, description, posts) |
| `linkedin.com/company/<slug>/jobs` | Job listings for the company |
| `linkedin.com/in/<person-slug>` | Person profile (public fields only) |
| `linkedin.com/posts/<id>` | Single post |
| `linkedin.com/jobs/view/<id>` | Single job listing |

---

## Step 2 — Bot-block reality check

LinkedIn blocks most automated fetches. Work through this decision tree before attempting:

```
Is this a company page (not a person profile)?
  └─ Yes → Try Step 3 (Firecrawl + archive.ph + Google cache)

Is the specific content already on a person's public profile?
  └─ Yes, and they have a custom URL → Try Step 3 (lower success rate)
  └─ No, profile is private or requires login → STOP. Note: linkedin_blocked: true

Is the goal just to get key facts (employees, founded, HQ)?
  └─ Yes → Crunchbase or company website is a better source (see wiki-extract-crunchbase)
```

---

## Step 3 — Fetch hierarchy

Work through these in order; stop at the first one that returns > 300 words of actual content.

### Option A — Firecrawl (first attempt)

```bash
COMPANY_SLUG="<company-name>"
OUT_DIR="raw/companies/${COMPANY_SLUG}/linkedin"
mkdir -p "$OUT_DIR"

llm-wiki ingest firecrawl \
  "https://www.linkedin.com/company/${COMPANY_SLUG}/" \
  --out "${OUT_DIR}/company.md"

# Verify: check if output has > 300 words of actual content
wc -w "${OUT_DIR}/company.md"
```

### Option B — archive.ph

```bash
URL="https://www.linkedin.com/company/${COMPANY_SLUG}/"
llm-wiki ingest firecrawl "https://archive.ph/${URL}" \
  --out "${OUT_DIR}/company.md"
```

### Option C — Google cache

```bash
URL="https://www.linkedin.com/company/${COMPANY_SLUG}/"
llm-wiki ingest firecrawl \
  "https://webcache.googleusercontent.com/search?q=cache:${URL}" \
  --out "${OUT_DIR}/company.md"
```

Note: Google cache availability varies; Google may have dropped some LinkedIn pages.

### Option D — Google search snippet (last resort)

When no cached copy is available, a Google search for `site:linkedin.com/company/<slug>` often returns the company description snippet:

```bash
QUERY="site:linkedin.com/company/${COMPANY_SLUG}"
ENCODED=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$QUERY")

llm-wiki ingest firecrawl \
  "https://www.google.com/search?q=${ENCODED}" \
  --out "${OUT_DIR}/google-snippet.md"
```

This won't give the full profile, but captures the company description, employee count, and industry from Google's index.

---

## Step 4 — Job listings

Job listings are more consistently accessible than profiles:

```bash
# Company job listings (paginated)
llm-wiki ingest firecrawl \
  "https://www.linkedin.com/jobs/search/?f_C=<company-id>&location=<location>" \
  --out "${OUT_DIR}/jobs.md"

# Single job listing
JOB_ID="<job listing ID>"
llm-wiki ingest firecrawl \
  "https://www.linkedin.com/jobs/view/${JOB_ID}/" \
  --out "${OUT_DIR}/job-${JOB_ID}.md"

# Alternative: LinkedIn jobs via Google search (more reliable)
QUERY="site:linkedin.com/jobs \"<company name>\" software engineer"
ENCODED=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$QUERY")
llm-wiki ingest firecrawl \
  "https://www.google.com/search?q=${ENCODED}" \
  --out "${OUT_DIR}/jobs-google.md"
```

---

## Step 5 — Manual export (highest fidelity)

If automated access is blocked and the content is important:

1. Ask the user to visit the LinkedIn page in their browser.
2. Ask them to copy the full page text (Ctrl+A, Ctrl+C) and paste it into a file:
   ```bash
   # User pastes content into:
   nano raw/companies/${COMPANY_SLUG}/linkedin/company-manual.txt
   ```
3. Then run **wiki-raw-prepare** to clean and structure the pasted text.

For job listings: LinkedIn's "Save as PDF" or browser print-to-PDF also works well.

---

## Step 6 — Supplement with better sources

LinkedIn is often redundant with cleaner sources. Before spending time on bypass attempts:

| If you need... | Better source |
|----------------|---------------|
| Employee count, funding, investors | **wiki-extract-crunchbase** |
| Company description, products | Company website → **wiki-research-web** |
| Recent company news | **wiki-research-news** |
| Job role patterns / hiring trends | Direct career page scrape → **wiki-research-web** |
| Founder background | Wikipedia → **wiki-extract-wikipedia** |

Only use this skill if the user specifically needs LinkedIn-sourced data (e.g. current open roles, LinkedIn-specific post content).

---

## Step 7 — Write to raw/ with frontmatter

Output path: `raw/companies/<slug>/linkedin/index.md`

```yaml
---
title: "<Company Name>"
source_url: https://www.linkedin.com/company/<slug>/
source_type: linkedin_company
linkedin_slug: "<slug>"
linkedin_blocked: false | true    # true if all bypass methods failed
bypass_method: firecrawl | archive.ph | google_cache | google_snippet | manual
employees_range: "<1-10|11-50|51-200|201-500|501-1000|1001-5000|5001-10000|10001+>"
industry: "<industry>"
headquarters: "<City, Country>"
founded: YYYY
fetched_date: YYYY-MM-DD
---
```

For person profiles:

```yaml
---
title: "<Full Name>"
source_url: https://www.linkedin.com/in/<slug>/
source_type: linkedin_person
linkedin_slug: "<slug>"
linkedin_blocked: false | true
current_title: "<title>"
current_company: "<company>"
fetched_date: YYYY-MM-DD
---
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Firecrawl returns "Join LinkedIn" page | Session cookie required; try archive.ph or Google cache |
| archive.ph returns "No snapshot available" | Request a new snapshot at `archive.ph/?run=1&url=<URL>` (may need CAPTCHA) |
| Google cache returns "did not match any documents" | LinkedIn page not indexed; use Google search snippet (Step 3 Option D) |
| All methods return < 300 words | Hard block; note `linkedin_blocked: true` and use Crunchbase instead |
| Person profile is private | Only public profile fields accessible; note in frontmatter |
| Job listing expired | Job may have been removed; note `status: expired` in frontmatter |
| Rate limit after multiple attempts | Wait 30 minutes between retries; LinkedIn rate-limits aggressively |

---

## Done looks like

- **Public-only** content captured; private/profile gaps called out in frontmatter.
- Bypass hierarchy tried in order; user informed when manual export is required.

## Related skills

- **wiki-extract-crunchbase** — almost always a better source for company facts; try this first
- **wiki-extract-wikipedia** — for well-known companies with Wikipedia articles
- **wiki-research-news** — for recent news about the company or person
- **wiki-research-web** — for company website, blog, and career page
- **wiki-raw-prepare** — clean and restructure scraped content before wiki ingestion

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

