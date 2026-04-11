<!-- Full procedure for **wiki-extract-annas**. Thin skill: `skills/wiki-extract-annas/SKILL.md`. -->

# Wiki extract — Anna's Archive

Searches Anna's Archive (the largest shadow library aggregator) for ebooks, papers, and documents, then downloads them into the vault for extraction. Use when:
- The user wants to research a book, paper, or document not available via standard web fetch.
- Content is paywalled or behind a publisher subscription.
- Building a literature collection on a topic.

**Requires:** `ANNAS_ARCHIVE_KEY` environment variable (Anna's Archive membership).

---

## Step 0 — Check credentials

```bash
# Check key is set
echo "${ANNAS_ARCHIVE_KEY:0:8}..."   # should print first 8 chars if set

# If not set, inform user:
# "ANNAS_ARCHIVE_KEY is required. Get a key at https://annas-archive.org/account"
```

If the key is not set, you can still search (no key needed for search) but cannot use the fast download API. Fall back to direct download links from search results.

---

## Step 1 — Search

### Search script

```bash
# Save as scripts/.tmp/annas_search.py
python3 << 'SCRIPT'
import urllib.request, urllib.parse, json, sys, os

API_KEY = os.environ.get('ANNAS_ARCHIVE_KEY', '')
BASE = 'https://annas-archive.org/api/search'

query = sys.argv[1] if len(sys.argv) > 1 else input('Search query: ')
fmt   = sys.argv[2] if len(sys.argv) > 2 else ''  # pdf, epub, mobi, etc.

params = {'q': query, 'lang': 'en', 'content': 'book', 'sort': 'most_relevant'}
if fmt:
    params['ext'] = fmt

url = f"{BASE}?{urllib.parse.urlencode(params)}"
req = urllib.request.Request(url, headers={
    'X-AA-Key': API_KEY,
    'User-Agent': 'wiki-llm-research/1.0'
})
with urllib.request.urlopen(req) as r:
    data = json.loads(r.read())

results = data.get('books', [])[:10]
for i, b in enumerate(results):
    print(f"{i+1}. [{b.get('ext','?')}] {b.get('title','?')} — {b.get('author','?')} ({b.get('year','?')}) — md5:{b.get('md5','?')}")
SCRIPT
```

**Usage:**
```bash
# Search by title and author
python3 scripts/.tmp/annas_search.py "Clean Code Robert Martin" pdf

# Search for a topic
python3 scripts/.tmp/annas_search.py "attention is all you need" pdf

# Search without format filter
python3 scripts/.tmp/annas_search.py "designing data intensive applications"
```

### Preferred formats for wiki ingestion

| Priority | Format | Why |
|----------|--------|-----|
| 1 | EPUB | Best text extraction, preserves structure |
| 2 | PDF | Common for papers; use marker adapter |
| 3 | MOBI / AZW3 | Calibre converts to EPUB |
| 4 | DJVU | Text extraction possible but lower quality |
| 5 | TXT | No extraction needed — use directly |

---

## Step 2 — Verify the result

Before downloading, confirm the result matches what was requested:
- Title contains the expected book/paper title.
- Author matches.
- Year is the expected edition (sort by year to get newest).
- Format is extractable (see priority above).

If the top result doesn't match, search more specifically (add author's last name, publication year, ISBN).

---

## Step 3 — Download

### Fast download API (requires key)

```bash
MD5="<from search result>"
FORMAT="epub"  # or pdf, mobi, etc.

python3 << 'SCRIPT'
import urllib.request, os, sys

API_KEY = os.environ['ANNAS_ARCHIVE_KEY']
MD5 = sys.argv[1]
FMT = sys.argv[2]

url = f"https://annas-archive.org/api/fast_download/{MD5}?key={API_KEY}"
req = urllib.request.Request(url, headers={'User-Agent': 'wiki-llm-research/1.0'})
with urllib.request.urlopen(req) as r:
    data = r.read()

outfile = f"/tmp/annas-{MD5}.{FMT}"
with open(outfile, 'wb') as f:
    f.write(data)
print(f"Downloaded: {outfile} ({len(data)//1024} KB)")
SCRIPT
python3 -c "..." "$MD5" "$FORMAT"
```

### Fallback — direct download link (no key)

Anna's Archive provides download links in search results that go through IPFS, Libgen, Z-Library mirrors, or slow download queues. These require a browser or extended wait:

```bash
# Fetch the book detail page to get download links
llm-wiki ingest firecrawl "https://annas-archive.org/md5/${MD5}" \
  --out /tmp/annas-detail.md
# Parse the output for download links
```

---

## Step 4 — Extract the downloaded file

Once downloaded, pass to **wiki-extract-ebook**:

```bash
# For EPUB:
python3 scripts/.tmp/extract_epub.py /tmp/annas-<md5>.epub raw/books/<slug>/full.md

# For PDF:
llm-wiki ingest marker /tmp/annas-<md5>.pdf --out books/<slug>/full.md
# Or PyMuPDF:
python3 scripts/.tmp/extract_pdf.py /tmp/annas-<md5>.pdf /tmp/extracted.txt
```

Follow the full extraction workflow in **wiki-extract-ebook** from Step 3 onward.

---

## Step 5 — Write to raw/ with frontmatter

Output path: `raw/books/<title-slug>/`

```yaml
---
title: "<Book Title>"
author: "<Author Name>"
source_type: ebook
source: annas-archive
annas_md5: "<md5>"
format: epub | pdf | mobi
isbn: "<if known>"
year: YYYY
downloaded_date: YYYY-MM-DD
---
```

---

## Step 6 — Return to orchestrator

After extraction and frontmatter are set, return to **wiki-research** Step 3 (post-process): validate, ingest, log.

---

## Ethics and scope

Anna's Archive aggregates content from shadow libraries (Libgen, Z-Library, Sci-Hub, etc.). Use for:
- Academic/research purposes.
- Books genuinely out of print or otherwise inaccessible.
- Papers locked behind publisher paywalls where an author copy doesn't exist.

Do not use for current commercial fiction or content where a legal purchase is straightforward.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ANNAS_ARCHIVE_KEY` not set | Register at https://annas-archive.org/account and export the key |
| Search returns no results | Try title-only search; remove author; check spelling |
| Fast download returns 403 | Key may be expired or quota exceeded; try slow download |
| Downloaded file won't open | File may be DRM-protected; check with `file` command |
| PDF is scanned (no text) | Use marker adapter (OCR) instead of PyMuPDF |
| EPUB extraction garbled | Run through **wiki-raw-prepare** to clean markdown |

---

## Done looks like

- Search results verified; download + **wiki-extract-ebook** (or PDF adapter) path chosen; **`raw/books/…`** markdown with frontmatter.
- Ethics scope respected (academic / inaccessible / out-of-print — not casual piracy of new commercial fiction).

## Related skills

- **wiki-extract-ebook** — extract downloaded files into text
- **wiki-extract-paywall** — for paywalled web articles (not books)
- **wiki-research-academic** — for papers via arXiv/DOI (preferred over Annas for open-access papers)
- **wiki-raw-prepare** — clean extracted markdown before wiki ingestion

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

