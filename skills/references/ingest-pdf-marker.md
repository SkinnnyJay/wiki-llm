# Ingest reference: PDF (Marker/Surya — free, local)

Use when you want free bulk PDF ingestion without an API key. Marker uses the Surya OCR engine, which significantly outperforms Tesseract on column layouts and mixed content. After ingest, run the standard prepare → validate → wiki-ingest flow.

**Important:** Marker is run in an isolated `.venv-marker` virtual environment to prevent dependency conflicts with the main venv (marker-pdf pins older anthropic/Pillow versions that break Vision/Claude API use).

## When to use vs Vision

| Adapter | Command | Cost | Quality | Best for |
|---------|---------|------|---------|----------|
| `pdf-marker` | `ingest pdf-marker` | Free (local) | Very good | Bulk ingestion, cost-sensitive batches |
| `pdf` (Vision) | `ingest pdf` | ~$0.02/page | Best | Difficult scans, spot-checking, targeted pages |

## Setup: isolated venv (required)

Marker must run in its own venv to avoid breaking Vision/Claude API compatibility:

```bash
# Create the isolated venv (one-time)
python3 -m venv .venv-marker
.venv-marker/bin/pip install marker-pdf
```

**Check it works:**
```bash
.venv-marker/bin/python -c "from marker.converters.pdf import PdfConverter; print('OK')"
```

**First run:** downloads ~1.5GB of Surya model weights automatically. Subsequent runs use cached models.

**No API key required. Main venv remains unaffected.**

### Secrets (optional `--use-llm`)

For LLM-assisted Marker mode, set keys in the **environment** — not on the shell command line (avoids exposing secrets in `ps` / process listings):

- Claude: `ANTHROPIC_API_KEY`
- Gemini: `GOOGLE_API_KEY` or `GEMINI_API_KEY`
- OpenAI: `OPENAI_API_KEY`

Deprecated CLI flags `--claude-api-key`, `--gemini-api-key`, and `--openai-api-key` still work for one release but print a warning and only copy the value into the subprocess environment (they are never passed as argv to the Marker worker).

## Run

```bash
llm-wiki ingest pdf-marker <path-to-pdf> --out <dest-under-raw>
# e.g.
llm-wiki ingest pdf-marker .tmp/PDFS/1880/issue.pdf --out pdfs/1880/issue.md
```

**Flags:**
- `--max-pages N` — cap page count (good for testing before full run)
- `--no-force-ocr` — let Marker decide per page (default forces OCR on all pages, correct for scanned historical PDFs)

## Config: set as default adapter

In `config.json`, set Marker as the default for all PDF ingestion:

```json
{
  "pdf": {
    "default_adapter": "pdf-marker",
    "max_cost_usd": 2.0
  }
}
```

When `max_cost_usd` is set, `ingest pdf` (Vision) will auto-fallback to `pdf-marker` if the estimated Vision cost exceeds the threshold, with a printed warning.

## Batch ingestion

```bash
# Uses pdf.default_adapter from vault config.json
python3 scripts/.tmp/batch_ingest_pdfs.py \
  --vault .tmp/vault-smoke/llm-wiki \
  --pdf-dir .tmp/PDFS

# Force Marker explicitly
python3 scripts/.tmp/batch_ingest_pdfs.py \
  --vault .tmp/vault-smoke/llm-wiki \
  --pdf-dir .tmp/PDFS \
  --adapter pdf-marker
```

## After ingest: prepare → validate

Output will be better than Tesseract but may still have OCR noise, especially on degraded pages. The prepare step (LLM formatting pass) is important:

1. **Prepare** — run `wiki-raw-prepare` skill or `llm-wiki raw prepare <path>`
2. **Validate** — `llm-wiki raw finish <path> -m "Marker OCR: heading structure, paragraph flow"`
3. **Merge** — run `wiki-ingest` skill

## Cost estimate

Free. Only cost is compute time (CPU: ~1–2 min/page; GPU: much faster).
