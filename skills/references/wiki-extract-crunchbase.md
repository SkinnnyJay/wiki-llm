<!-- Full procedure for **wiki-extract-crunchbase**. Thin skill: `skills/wiki-extract-crunchbase/SKILL.md`. -->

# Wiki extract — Crunchbase

Extracts structured startup and investor data from Crunchbase into `raw/` for wiki ingestion. Use when:
- Researching a startup's funding history, investors, or team.
- Building a competitive landscape or market map.
- "Get the Crunchbase profile for X", "what funding has X raised?", "who are X's investors?".

---

## Step 1 — Identify the URL type

| URL pattern | Content |
|-------------|---------|
| `crunchbase.com/organization/<slug>` | Company profile (funding, team, investors) |
| `crunchbase.com/person/<slug>` | Founder/investor profile |
| `crunchbase.com/funding_round/<uuid>` | Single funding round details |
| `crunchbase.com/investor/<slug>` | Investment firm portfolio |
| Crunchbase search / discover page | Filtered company list |

---

## Step 2 — Check credentials

Crunchbase has two tiers: public web pages (no key needed, JS-heavy) and the Crunchbase Basic API (free with key, 200 req/day).

```bash
# Check for API key
echo "${CRUNCHBASE_API_KEY:0:8}..."

# If set, use API (Step 3). Otherwise use Firecrawl on web pages (Step 4).
```

Register for a free Basic API key at: https://www.crunchbase.com/account/user_key

---

## Step 3 — Crunchbase Basic API (preferred if key available)

```bash
ORG_SLUG="<company-name>"   # e.g. "stripe", "openai"
OUT_DIR="raw/companies/${ORG_SLUG}"
mkdir -p "$OUT_DIR"

# Organization profile
curl -s "https://api.crunchbase.com/api/v4/entities/organizations/${ORG_SLUG}?user_key=${CRUNCHBASE_API_KEY}&field_ids=short_description,founded_on,funding_stage,funding_total,num_funding_rounds,num_employees_enum,ipo_status,website_url,twitter_url,linkedin_url,categories,location_identifiers,short_description" \
  > "${OUT_DIR}/org.json"

# Funding rounds
curl -s "https://api.crunchbase.com/api/v4/entities/organizations/${ORG_SLUG}/funding_rounds?user_key=${CRUNCHBASE_API_KEY}&field_ids=announced_on,money_raised,investment_type,lead_investor_identifiers,investor_identifiers" \
  > "${OUT_DIR}/funding.json"
```

Parse to markdown:

```python
# scripts/.tmp/parse_crunchbase.py
import json, pathlib, sys

org = json.loads(pathlib.Path(sys.argv[1]).read_text())['properties']
funding = json.loads(pathlib.Path(sys.argv[2]).read_text()).get('entities', [])

print(f"# {org.get('identifier',{}).get('value','?')}")
print(f"\n{org.get('short_description','')}")
print(f"\n**Founded:** {org.get('founded_on',{}).get('value','?')}")
print(f"**Stage:** {org.get('funding_stage','?')}")
print(f"**Total funding:** {org.get('funding_total',{}).get('value_usd','?')}")
print(f"\n## Funding Rounds\n")

for r in funding:
    p = r.get('properties', {})
    leads = ', '.join(i.get('value','?') for i in p.get('lead_investor_identifiers', []))
    print(f"- **{p.get('announced_on',{}).get('value','?')}** — {p.get('investment_type','?')} "
          f"${p.get('money_raised',{}).get('value_usd','?'):,} | Lead: {leads or 'undisclosed'}")
```

```bash
python3 scripts/.tmp/parse_crunchbase.py \
  "${OUT_DIR}/org.json" "${OUT_DIR}/funding.json" > "${OUT_DIR}/index.md"
```

---

## Step 4 — Firecrawl web scrape (no API key)

Crunchbase is heavily JavaScript-rendered. Firecrawl handles this well; stdlib will return an empty shell.

```bash
ORG_SLUG="<company-name>"
OUT_DIR="raw/companies/${ORG_SLUG}"
mkdir -p "$OUT_DIR"

# Company profile page
llm-wiki ingest firecrawl \
  "https://www.crunchbase.com/organization/${ORG_SLUG}" \
  --out "${OUT_DIR}/profile.md"

# Person profile
llm-wiki ingest firecrawl \
  "https://www.crunchbase.com/person/<person-slug>" \
  --out "raw/people/<person-slug>/crunchbase.md"
```

If Crunchbase blocks the crawler (returns login page or < 200 words), try:

```bash
# archive.ph often has Crunchbase snapshots
llm-wiki ingest firecrawl \
  "https://archive.ph/https://www.crunchbase.com/organization/${ORG_SLUG}" \
  --out "${OUT_DIR}/profile.md"
```

---

## Step 5 — Supplement with news and LinkedIn

Crunchbase profiles often link to recent news and LinkedIn. After extracting the profile:

```bash
# Fetch recent news mentions (from the News tab)
llm-wiki ingest firecrawl \
  "https://www.crunchbase.com/organization/${ORG_SLUG}/recent_news" \
  --out "${OUT_DIR}/news.md"

# For LinkedIn (company page) — invoke wiki-extract-linkedin
# See skills/references/wiki-extract-linkedin.md
```

---

## Step 6 — Write to raw/ with frontmatter

Output path: `raw/companies/<slug>/index.md`

```yaml
---
title: "<Company Name>"
slug: "<crunchbase-slug>"
source_url: https://www.crunchbase.com/organization/<slug>
source_type: crunchbase_org
founded: YYYY
hq_location: "<City, Country>"
funding_stage: seed | series_a | series_b | ... | ipo | acquired
funding_total_usd: <N>
num_funding_rounds: <N>
num_employees: 1-10 | 11-50 | 51-100 | 101-250 | 251-500 | 501-1000 | 1001-5000 | 5001-10000 | 10001+
categories: [<tag1>, <tag2>]
investors: [<investor1>, <investor2>]
website: https://...
fetched_date: YYYY-MM-DD
data_source: crunchbase_api | crunchbase_web | archive
---
```

For person profiles:

```yaml
---
title: "<Full Name>"
source_url: https://www.crunchbase.com/person/<slug>
source_type: crunchbase_person
role: founder | investor | executive
companies: [<company1>, <company2>]
fetched_date: YYYY-MM-DD
---
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| API returns 401 | `CRUNCHBASE_API_KEY` is invalid or expired; regenerate at crunchbase.com |
| API returns 429 | Free tier limit (200/day) hit; wait 24h or switch to Firecrawl scrape |
| Firecrawl returns login page | Crunchbase has blocked the crawler IP; try archive.ph snapshot |
| Funding total is `null` | Company has undisclosed funding; note `funding_total_usd: undisclosed` |
| Profile shows "0 employees" | Crunchbase may not have employee data; supplement from LinkedIn |

---

## Done looks like

- Company profile + funding summary in **`raw/`** when accessible; paywall/login failures noted without fabricated metrics.

## Related skills

- **wiki-extract-linkedin** — for company/person data from LinkedIn to supplement Crunchbase
- **wiki-research-news** — for recent news mentions of the company
- **wiki-research-web** — for company website, blog, and press releases
- **wiki-raw-prepare** — clean and restructure extracted data before wiki ingestion

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

