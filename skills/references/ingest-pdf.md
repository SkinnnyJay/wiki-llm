# Ingest reference: PDF

Use this when a user wants to ingest a `.pdf` file into `raw/`.

## Approach

Claude Vision — every page is converted to a high-DPI image and transcribed by the Anthropic API. No Tesseract. No MarkItDown. Works on scanned and text-layer PDFs equally.

## Dependencies

**Check first:**
```bash
python3 -c "import pdf2image, anthropic; print('OK')"
pdftoppm -v 2>&1 | head -1
```

**Install if missing:**
```bash
# Python deps (from repo root, in a venv)
python3 -m venv .venv && .venv/bin/pip install pdf2image anthropic

# System dep — poppler (macOS)
brew install poppler
```

**API key:** `ANTHROPIC_API_KEY` must be set in env or `~/.claude/settings.local.json` → `env`.

## Run

```bash
llm-wiki ingest pdf <path-to-pdf> --out <dest-under-raw>
# e.g.
llm-wiki ingest pdf .tmp/PDFS/1880/issue.pdf --out pdfs/1880/issue.md
```

**Flags:**
- `--dpi 300` — image resolution per page (default: 300; raise to 400 for very small print)
- `--max-pages N` — cap page count before running (cost control)
- `--model <id>` — override Claude model (default: `claude-sonnet-4-5-20250929`)

## After ingest: prepare → validate

1. **Prepare** (heavy lifting — LLM formats transcript into clean markdown):
   Run the `wiki-raw-prepare` skill, or:
   ```bash
   llm-wiki raw prepare <path-under-raw>
   ```

2. **Validate** (structural compliance + autofix):
   ```bash
   llm-wiki raw finish <path-under-raw> -m "Describe what was cleaned"
   ```
   This runs autofix, validates, logs to `raw/.preparation-log.jsonl`, and commits `[prepare]` to vault git.

3. **Merge to wiki** — run `wiki-ingest` skill.

## Cost estimate

~1,500–3,000 input tokens per page (image) + ~500–1,000 output tokens per page.
A 100-page issue ≈ $0.50–$2.00 at Sonnet pricing. Use `--max-pages` to test on a subset first.
