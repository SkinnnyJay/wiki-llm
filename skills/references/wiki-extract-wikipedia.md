<!-- Full procedure for **wiki-extract-wikipedia**. Thin skill: `skills/wiki-extract-wikipedia/SKILL.md`. -->

# Wiki extract — Wikipedia

Extracts Wikipedia articles and Wikidata structured data into `raw/` for wiki ingestion. Use when:
- Capturing an encyclopedia article as a reference baseline for a topic.
- Extracting structured infobox data (dates, classifications, identifiers) via Wikidata.
- "Get the Wikipedia article on X", "add Wikipedia's page for Y to the vault", "extract infobox data for Z".

Prefer this over `wiki-research-web` + plain fetch for Wikipedia: the MediaWiki API returns clean, structured markdown without sidebar noise, and Wikidata provides machine-readable infobox data.

---

## Step 1 — Identify the input

| Input | Action |
|-------|--------|
| Wikipedia URL (`en.wikipedia.org/wiki/<Title>`) | Extract by title (Step 2) |
| Article title or topic name | Extract by title (Step 2) |
| Wikidata QID (`Q12345`) | Fetch structured data directly (Step 4) |
| Wikipedia search query | Search first (Step 5) |

---

## Step 2 — Extract article via Wikipedia REST API

The Wikipedia REST API returns clean HTML/Markdown without sidebar, navigation, or ad noise — much cleaner than Firecrawl on the article page.

```bash
TITLE="<Article_Title>"        # use underscores or URL-encoded spaces
LANG="en"                      # language code
SLUG="${TITLE,,}"               # lowercase slug
SLUG="${SLUG// /-}"             # spaces to hyphens
OUT_DIR="raw/reference/wikipedia"
mkdir -p "$OUT_DIR"

# Summary (intro paragraph + infobox metadata) — always start here
curl -s "https://en.wikipedia.org/api/rest_v1/page/summary/${TITLE}" \
  -H "Accept: application/json" \
  -H "User-Agent: wiki-llm-research/1.0 (contact@example.com)" \
  > "/tmp/wp-summary.json"

python3 << 'PYEOF'
import json, sys, pathlib

data = json.loads(pathlib.Path('/tmp/wp-summary.json').read_text())
print(f"Title:       {data.get('title','?')}")
print(f"Description: {data.get('description','?')}")
print(f"Extract:     {data.get('extract','?')[:500]}")
print(f"Wikidata QID: {data.get('wikibase_item','?')}")
print(f"Thumbnail:   {data.get('thumbnail',{}).get('source','none')}")
PYEOF
```

---

## Step 3 — Extract full article text

```bash
# Full article as plain text (Markdown-like, sections preserved)
curl -s "https://en.wikipedia.org/api/rest_v1/page/mobile-sections/${TITLE}" \
  -H "Accept: application/json" \
  -H "User-Agent: wiki-llm-research/1.0" \
  > "/tmp/wp-full.json"

python3 << 'PYEOF'
import json, pathlib, re
from html.parser import HTMLParser

class StripTags(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []
    def handle_data(self, d):
        self._parts.append(d)
    def get_text(self):
        return ''.join(self._parts)

data    = json.loads(pathlib.Path('/tmp/wp-full.json').read_text())
lead    = data.get('lead', {})
sections= data.get('remaining', {}).get('sections', [])

def strip_html(html):
    p = StripTags()
    p.feed(html or '')
    return re.sub(r'\n{3,}', '\n\n', p.get_text()).strip()

out = [f"# {lead.get('displaytitle', '?')}\n"]
out.append(strip_html(lead.get('sections',[{}])[0].get('content','')))

for sec in sections:
    level = '#' * min(sec.get('toclevel', 2) + 1, 4)
    title = sec.get('line', '')
    out.append(f"\n{level} {title}\n")
    out.append(strip_html(sec.get('content','')))

print('\n'.join(out))
PYEOF
python3 -c "..." > "${OUT_DIR}/${SLUG}.md"
```

Alternatively, use the Wikimedia action API for raw wikitext:

```bash
ENCODED=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$TITLE")

curl -s "https://en.wikipedia.org/w/api.php?action=query&titles=${ENCODED}&prop=revisions&rvprop=content&rvslots=main&format=json" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
pages = data['query']['pages']
for p in pages.values():
    content = p.get('revisions',[{}])[0].get('slots',{}).get('main',{}).get('*','')
    print(content[:5000])  # first 5000 chars of wikitext
"
```

---

## Step 4 — Wikidata structured data

Wikidata provides machine-readable infobox data for any Wikipedia article. Use the QID from Step 2.

```bash
QID="Q12345"   # from summary.wikibase_item

# Fetch entity data
curl -s "https://www.wikidata.org/wiki/Special:EntityData/${QID}.json" \
  -H "User-Agent: wiki-llm-research/1.0" \
  > "/tmp/wd-${QID}.json"

python3 << 'PYEOF'
import json, pathlib, sys

QID   = sys.argv[1]
data  = json.loads(pathlib.Path(f'/tmp/wd-{QID}.json').read_text())
ent   = data['entities'][QID]
label = ent.get('labels',{}).get('en',{}).get('value','?')
desc  = ent.get('descriptions',{}).get('en',{}).get('value','?')
claims= ent.get('claims',{})

# Common useful properties
PROPS = {
    'P31':  'instance_of',
    'P18':  'image',
    'P571': 'inception_date',
    'P576': 'dissolved_date',
    'P17':  'country',
    'P131': 'located_in',
    'P856': 'official_website',
    'P154': 'logo',
    'P159': 'headquarters',
    'P169': 'ceo',
    'P112': 'founded_by',
    'P452': 'industry',
    'P1128':'employees',
}

print(f"QID:   {QID}")
print(f"Label: {label}")
print(f"Desc:  {desc}")

for pid, pname in PROPS.items():
    vals = claims.get(pid, [])
    for val in vals[:2]:
        main = val.get('mainsnak',{}).get('datavalue',{})
        dtype = main.get('type','')
        if dtype == 'string':
            print(f"{pname}: {main.get('value','?')}")
        elif dtype == 'time':
            print(f"{pname}: {main.get('value',{}).get('time','?')}")
        elif dtype == 'wikibase-entityid':
            inner_qid = main.get('value',{}).get('id','?')
            print(f"{pname}: {inner_qid}")
PYEOF
python3 -c "..." "$QID" > "${OUT_DIR}/${SLUG}-wikidata.txt"
```

For complex SPARQL queries against Wikidata:

```bash
# Example: find all companies in a sector
SPARQL='SELECT ?company ?companyLabel WHERE {
  ?company wdt:P31 wd:Q4830453 .  # instance of: business
  ?company wdt:P452 wd:Q11661 .   # industry: information technology
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
} LIMIT 20'

curl -s -G "https://query.wikidata.org/sparql" \
  --data-urlencode "query=${SPARQL}" \
  -H "Accept: application/json" \
  -H "User-Agent: wiki-llm-research/1.0" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
for b in data['results']['bindings']:
    print(b['companyLabel']['value'])
"
```

---

## Step 5 — Wikipedia search

```bash
QUERY="<search terms>"
ENCODED=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$QUERY")

curl -s "https://en.wikipedia.org/api/rest_v1/page/search/title?q=${ENCODED}&limit=10" \
  -H "User-Agent: wiki-llm-research/1.0" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
for p in data.get('pages', []):
    print(f\"{p.get('title','?'):40} {p.get('description','')[:80]}\")
"
```

Present the list to the user and confirm which article to extract.

---

## Step 6 — Write to raw/ with frontmatter

Output path: `raw/reference/wikipedia/<slug>.md`

```yaml
---
title: "<Article Title>"
source_url: https://en.wikipedia.org/wiki/<Title>
source_type: wikipedia_article
wikidata_qid: "<Q12345>"
language: en
last_edited: YYYY-MM-DD         # from summary.timestamp
fetched_date: YYYY-MM-DD
# Wikidata fields (add whichever are populated):
instance_of: "<type>"
country: "<country QID or name>"
inception_date: YYYY-MM-DD
official_website: https://...
---
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| API returns 404 | Title may use different capitalization; search first (Step 5) |
| Summary returns disambiguation page | Multiple articles match; search and select the correct one |
| Full article is very long (>10,000 words) | Extract only lead section + specific sections; ask user which sections to include |
| Wikidata QID not in summary | Look up the article title at `wikidata.org` search |
| SPARQL query times out | Add `LIMIT 100` or narrow the filter; Wikidata SPARQL has a 60s timeout |
| Non-English Wikipedia | Change `en.wikipedia.org` to `<lang>.wikipedia.org` throughout |

---

## Done looks like

- Article text + structured metadata in **`raw/`**; Wikidata block included when fetched; API/rest errors surfaced (no invented infobox facts).

## Related skills

- **wiki-research-academic** — for peer-reviewed sources linked from Wikipedia's references
- **wiki-research-web** — for supplementary sources beyond the article
- **wiki-extract-crunchbase** — for company articles to supplement with funding/investor data
- **wiki-raw-prepare** — clean and restructure extracted article markdown before wiki ingestion

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

