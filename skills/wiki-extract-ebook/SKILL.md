---
name: wiki-extract-ebook
description: Extract text from EPUB, MOBI, PDF, and AZW3 ebook files into raw/. Use when user has a local ebook or PDF to add to the vault.
disable-model-invocation: true
argument-hint: "<file path to ebook>"
---

# Wiki extract — ebook

Converts local ebook files (EPUB, MOBI, PDF, AZW3, DJVU) to clean markdown and writes them to `raw/`. Use when:
- The user drops an ebook or PDF into the vault.
- A downloaded paper/book needs to be extracted before wiki ingestion.
- A PDF was fetched by an adapter but produced garbled output.

For downloading ebooks first, see **wiki-extract-annas**.

---

## Setup (one-time, per format)

Check what's available:

```bash
# EPUB
python3 -c "import ebooklib, bs4; print('epub: ok')" 2>/dev/null || \
  pip install ebooklib beautifulsoup4

# PDF (PyMuPDF — fast, handles most PDFs)
python3 -c "import fitz; print('pdf/pymupdf: ok')" 2>/dev/null || \
  pip install pymupdf

# PDF (Marker — AI-powered, better for academic papers with equations/tables)
which marker 2>/dev/null || pip install marker-pdf

# MOBI / AZW3 (requires Calibre)
which ebook-convert 2>/dev/null || echo "Install Calibre: https://calibre-ebook.com/download"

# DJVU (requires djvulibre)
which ddjvu 2>/dev/null || brew install djvulibre
```

---

## Step 1 — Identify the file format and choose extractor

| Format | Preferred extractor | Fallback |
|--------|--------------------|---------| 
| `.epub` | ebooklib + BeautifulSoup | Calibre `ebook-convert epub txt` |
| `.pdf` (academic paper) | llm-wiki marker adapter | PyMuPDF |
| `.pdf` (scanned / image-only) | marker adapter (OCR mode) | Tesseract |
| `.mobi` / `.azw3` | Calibre `ebook-convert` → EPUB → ebooklib | Calibre direct to txt |
| `.djvu` | `ddjvu -format=text` | Calibre |

---

## Step 2 — Extract content

### EPUB (ebooklib)

```python
# scripts/.tmp/extract_epub.py
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import sys, pathlib

def epub_to_text(epub_path):
    book = epub.read_epub(epub_path)
    parts = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        parts.append(soup.get_text(separator='\n', strip=True))
    return '\n\n---\n\n'.join(parts)

if __name__ == '__main__':
    text = epub_to_text(sys.argv[1])
    pathlib.Path(sys.argv[2]).write_text(text)
    print(f"Extracted {len(text)} chars to {sys.argv[2]}")
```

```bash
python3 scripts/.tmp/extract_epub.py /path/to/book.epub /tmp/book-extracted.txt
```

### PDF (PyMuPDF — fast)

```python
# scripts/.tmp/extract_pdf.py
import fitz  # PyMuPDF
import sys, pathlib

def pdf_to_text(pdf_path):
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return '\n\n---\n\n'.join(pages)

if __name__ == '__main__':
    text = pdf_to_text(sys.argv[1])
    pathlib.Path(sys.argv[2]).write_text(text)
    print(f"Extracted {len(text)} chars from {len(fitz.open(sys.argv[1]))} pages")
```

```bash
python3 scripts/.tmp/extract_pdf.py /path/to/paper.pdf /tmp/paper-extracted.txt
```

### PDF (marker adapter — best for academic papers)

```bash
# If marker is installed and configured in llm-wiki:
llm-wiki ingest marker /path/to/paper.pdf \
  --out academic/<year>/<slug>.md
```

Marker handles equations, tables, and multi-column layouts better than PyMuPDF. Check `llm-wiki integrations status` to confirm it's available.

### MOBI / AZW3 (Calibre)

```bash
# Convert to EPUB first, then use ebooklib above
ebook-convert /path/to/book.mobi /tmp/book-converted.epub
python3 scripts/.tmp/extract_epub.py /tmp/book-converted.epub /tmp/book-extracted.txt

# Or convert directly to plain text:
ebook-convert /path/to/book.mobi /tmp/book.txt --txt-output-formatting=markdown
```

### DJVU

```bash
ddjvu -format=text /path/to/book.djvu /tmp/book-extracted.txt
```

---

## Step 3 — Chunk large texts

Ebooks can be very long. Do not write a single 200,000-word file to `raw/` — split by chapter or section:

```python
# Simple chapter splitter (for epub output with '---' separators)
with open('/tmp/book-extracted.txt') as f:
    content = f.read()

chapters = content.split('\n\n---\n\n')
for i, chapter in enumerate(chapters):
    if len(chapter.strip()) < 100:
        continue  # skip near-empty chapters
    with open(f'raw/books/<slug>/chapter-{i+1:03d}.md', 'w') as f:
        f.write(chapter)
```

For research purposes, you often only need specific chapters — ask the user which sections are relevant before extracting the full book.

---

## Step 4 — Write to raw/ with frontmatter

Output path: `raw/books/<title-slug>/<chapter-or-full>.md`

```bash
# Prepend frontmatter to extracted file
cat > raw/books/<slug>/full.md << 'EOF'
---
title: "<Book Title>"
author: "<Author Name>"
source_type: ebook
format: epub | pdf | mobi | azw3 | djvu
source_file: /path/to/original/file
isbn: "<ISBN if known>"
year: YYYY
extracted_date: YYYY-MM-DD
extractor: ebooklib | pymupdf | marker | calibre | ddjvu
---

EOF
cat /tmp/book-extracted.txt >> raw/books/<slug>/full.md
```

---

## Step 5 — Evaluate and return to orchestrator

Large texts need trimmed evaluation — check:
- Is the extracted text readable (not garbled OCR)?
- Are there relevant chapters/sections for the research question?
- Does it pass the prompt-injection check (`llm_wiki_security.prompt_injection`)?

Then return to **wiki-research** Step 3 (post-process) or the invoking skill.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| ebooklib `DRMException` | File has DRM; use Calibre DeDRM plugin first |
| PyMuPDF returns empty pages | Scanned PDF (image-only); switch to marker or Tesseract |
| Calibre not found | `brew install calibre` (macOS) or download from calibre-ebook.com |
| Marker produces garbled math | Expected for complex equations; note `[OCR_QUALITY: medium]` in frontmatter |
| EPUB has no text (just images) | Comic/illustrated book; not suitable for text extraction |
| Output file > 1 MB | Split into chapters (Step 3) |

---

## Done looks like

- **`raw/books/…` or agreed path** contains extracted markdown with format metadata and chapter splits when needed.
- OCR/extraction quality noted in frontmatter when marginal.

## Related skills

- **wiki-extract-annas** — search and download ebooks before extracting
- **wiki-extract-paywall** — bypass paywalled PDF landing pages
- **wiki-raw-prepare** — clean structurally broken markdown after extraction
- **wiki-research-academic** — for academic PDFs fetched from arXiv/DOI

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

