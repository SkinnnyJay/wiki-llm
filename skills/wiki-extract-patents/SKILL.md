---
name: wiki-extract-patents
description: Extract patent text, claims, and citations from Google Patents, Espacenet, USPTO into raw/. Use for IP and prior art research.
disable-model-invocation: true
argument-hint: "<patent number or search query>"
---

# Wiki extract — patents

Extracts full patent documents from Google Patents, Espacenet (European Patent Office), and USPTO into `raw/` for wiki ingestion. Use when:
- Researching prior art or patentability for a technology area.
- Extracting technical disclosures from patents for knowledge capture.
- "Get this patent", "find patents for X", "what's in this patent number?", "prior art search for Y".

---

## Step 1 — Identify the input type

| Input | Action |
|-------|--------|
| Patent number (e.g. `US10234567B2`, `EP3456789A1`, `WO2023123456A1`) | Direct fetch (Step 2) |
| Google Patents URL (`patents.google.com/patent/<ID>`) | Direct fetch (Step 3) |
| Espacenet URL (`worldwide.espacenet.com/...`) | Direct fetch (Step 4) |
| USPTO URL (`patents.google.com` or `patents.justia.com`) | Direct fetch (Step 3 or 5) |
| Topic / keyword search | Search first (Step 6) |

### Patent number format reference

| Prefix | Office | Example |
|--------|--------|---------|
| US | United States (USPTO) | `US10234567B2` |
| EP | Europe (EPO) | `EP3456789A1` |
| WO | International (WIPO PCT) | `WO2023123456A1` |
| CN | China (CNIPA) | `CN115678901A` |
| JP | Japan (JPO) | `JP2023123456A` |
| GB | United Kingdom (UKIPO) | `GB2612345A` |

---

## Step 2 — Fetch by patent number (quickest path)

Google Patents accepts any patent number directly:

```bash
PATENT_NUM="US10234567B2"   # adjust as needed
SLUG="${PATENT_NUM,,}"       # lowercase
OUT_DIR="raw/patents/${SLUG}"
mkdir -p "$OUT_DIR"

# Google Patents canonical URL
GPAT_URL="https://patents.google.com/patent/${PATENT_NUM}/en"

llm-wiki ingest firecrawl "$GPAT_URL" --out "${OUT_DIR}/patent.md"
# Fallback (no JS rendering but works for most patents):
llm-wiki ingest url "$GPAT_URL" --out "${OUT_DIR}/patent.md"
```

---

## Step 3 — Google Patents

Google Patents is the most accessible source: it indexes USPTO, EPO, WIPO, and many national offices, and provides clean text rendering.

```bash
# Full text page (abstract + claims + description)
PATENT_NUM="US10234567B2"
llm-wiki ingest firecrawl \
  "https://patents.google.com/patent/${PATENT_NUM}/en" \
  --out "${OUT_DIR}/patent.md"
```

### Google Patents JSON API (structured data)

Google Patents exposes a semi-public JSON endpoint:

```bash
python3 << 'PYEOF'
import urllib.request, json, sys

patent_num = sys.argv[1]  # e.g. "US10234567B2"
url = f"https://patents.google.com/api/query?id=patent/{patent_num}&hl=en"

req = urllib.request.Request(url, headers={
    'User-Agent': 'wiki-llm-research/1.0',
    'Accept': 'application/json'
})
with urllib.request.urlopen(req) as r:
    data = json.loads(r.read())

hits = data.get('hits', {}).get('hit', [])
if hits:
    p = hits[0]
    print(f"Title:    {p.get('title', '?')}")
    print(f"Assignee: {', '.join(p.get('assignee', []))}")
    print(f"Inventor: {', '.join(p.get('inventor', []))}")
    print(f"Filed:    {p.get('filing_date', '?')}")
    print(f"Granted:  {p.get('grant_date', '?')}")
    print(f"Abstract: {p.get('abstract', '?')[:500]}")
    print(f"CPC:      {', '.join(p.get('cpc', [])[:5])}")
    print(f"Citations: {p.get('citation_count', '?')}")
PYEOF
python3 -c "..." "$PATENT_NUM" > "${OUT_DIR}/meta.txt"
```

---

## Step 4 — Espacenet (EPO)

For European and PCT patents, Espacenet provides a clean fulltext API:

```bash
# Espacenet OPS API (Open Patent Services) — free, no key needed for basic queries
PATENT_NUM="EP3456789A1"
DOCDB_ID="${PATENT_NUM:0:2}.${PATENT_NUM:2}"   # format: EP.3456789A1

# Bibliographic data
curl -s "https://ops.epo.org/3.2/rest-services/published-data/publication/epodoc/${PATENT_NUM}/biblio" \
  -H "Accept: application/json" \
  > "${OUT_DIR}/biblio.json"

# Fulltext (claims + description) — HTML format
curl -s "https://ops.epo.org/3.2/rest-services/published-data/publication/epodoc/${PATENT_NUM}/description" \
  -H "Accept: application/json" \
  > "${OUT_DIR}/description.json"

# Claims
curl -s "https://ops.epo.org/3.2/rest-services/published-data/publication/epodoc/${PATENT_NUM}/claims" \
  -H "Accept: application/json" \
  > "${OUT_DIR}/claims.json"
```

Note: OPS API has a daily quota (4,000 calls/day). Authenticate with `ESPACENET_CLIENT_ID` + `ESPACENET_CLIENT_SECRET` (free registration at https://developers.epo.org) for higher limits.

---

## Step 5 — USPTO full text (Justia fallback)

For US patents, Justia provides clean plain-text rendering without JS:

```bash
# Justia patent pages are stdlib-accessible
PATENT_NUM="10234567"   # numeric only, no "US" prefix
llm-wiki ingest url \
  "https://patents.justia.com/patent/${PATENT_NUM}" \
  --out "${OUT_DIR}/patent.md"
```

---

## Step 6 — Prior art keyword search

```bash
QUERY="<technology description>"
ENCODED=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$QUERY")

# Google Patents search (sorted by relevance)
llm-wiki ingest firecrawl \
  "https://patents.google.com/patent/search?q=${ENCODED}&num=10" \
  --out "raw/patents/search-${QUERY// /-}.md"

# Google Patents advanced: filter by date, assignee, CPC code
# Example: US patents filed 2020-2024, assigned to OpenAI:
ADVANCED_URL="https://patents.google.com/patent/search?q=${ENCODED}&assignee=openai&before=priority:20241231&after=priority:20200101"
llm-wiki ingest firecrawl "$ADVANCED_URL" \
  --out "raw/patents/search-openai-${QUERY// /-}.md"
```

---

## Step 7 — Extract drawings descriptions

Patent drawings are images — extract the text descriptions from the "Brief Description of Drawings" section of the patent body:

```python
# scripts/.tmp/extract_patent_drawings.py
import re, sys, pathlib

text = pathlib.Path(sys.argv[1]).read_text()

# Find drawings section
match = re.search(
    r'(?:BRIEF DESCRIPTION OF (?:THE )?DRAWINGS?|DESCRIPTION OF DRAWINGS?)(.*?)(?=\n(?:DETAILED DESCRIPTION|DESCRIPTION OF EMBODIMENTS|CLAIMS)\n)',
    text, re.IGNORECASE | re.DOTALL
)
if match:
    print("## Brief Description of Drawings\n")
    print(match.group(1).strip())
else:
    print("No drawings description section found.")
```

---

## Step 8 — Write to raw/ with frontmatter

Output path: `raw/patents/<patent-number>/index.md`

```yaml
---
title: "<Patent Title>"
patent_number: "<US10234567B2>"
application_number: "<US16/123456>"
filing_date: YYYY-MM-DD
grant_date: YYYY-MM-DD
publication_date: YYYY-MM-DD
expiration_date: YYYY-MM-DD
assignee: "<Company or Individual>"
inventors: [<name1>, <name2>]
source_url: https://patents.google.com/patent/<ID>/en
source_type: patent
office: USPTO | EPO | WIPO | CNIPA | JPO | UKIPO
cpc_codes: [<H04L63/00>, <G06F16/00>]   # cooperative patent classification
status: active | expired | pending | abandoned
forward_citations: <N>
backward_citations: <N>
fetched_date: YYYY-MM-DD
data_source: google_patents | espacenet | justia | uspto
---
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Google Patents returns empty body | Patent may be image-only (scanned); try Justia or USPTO Full Text |
| Espacenet OPS returns 403 | Rate limit hit; wait 24h or register for authenticated access |
| Patent number not found | Try alternate format: `US 10,234,567 B2` → `US10234567B2` (remove spaces/commas) |
| PCT (WO) patent not in USPTO | WO patents are in Espacenet and Google Patents, not USPTO directly |
| Firecrawl times out | Google Patents can be slow; retry with `--timeout 60` if supported |
| Claims section is missing | Some patents have claims redacted; fetch the PDF version from Google Patents |

---

## Done looks like

- Patent identifier, title, and claims (or documented absence) in **`raw/`** with stable source URLs.
- Jurisdiction (US/EPO/WO) clear in frontmatter.

## Related skills

- **wiki-research-academic** — for academic papers that often cite or are cited by patents
- **wiki-research-web** — for news coverage or technical blog posts about a patent
- **wiki-extract-crunchbase** — for company context around a patent assignee
- **wiki-raw-prepare** — clean and restructure patent text before wiki ingestion

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

