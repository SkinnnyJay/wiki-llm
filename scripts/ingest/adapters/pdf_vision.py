"""PDF ingest adapter using Claude Vision (Anthropic API + pdf2image/poppler)."""
from __future__ import annotations

import base64
import io
import os
import shutil
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, ClassVar

from lib.paths import raw_destination

from ingest.base import Adapter, IngestResult

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_DPI = 300

_TRANSCRIPTION_PROMPT = (
    "Transcribe ALL text on this page exactly as it appears. "
    "Use markdown formatting (headings, lists, tables where appropriate). "
    "For any text that is illegible or uncertain, write [illegible] or [?]. "
    "Do NOT infer or fabricate any text — only transcribe what you can actually read. "
    "If this is a title page or table of contents, preserve the layout structure."
)


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------

def _has_pdf2image() -> bool:
    try:
        import pdf2image  # noqa: F401
        return True
    except ImportError:
        return False


def _has_anthropic() -> bool:
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def pdf_vision_preflight() -> str | None:
    """Return an error message if any dependency is missing, else None."""
    if not _has_pdf2image():
        return (
            "PDF Vision ingest requires pdf2image.\n"
            "  pip install pdf2image anthropic\n"
            "  brew install poppler  # macOS\n"
            "See: skills/references/ingest-pdf.md"
        )
    if not _has_anthropic():
        return (
            "PDF Vision ingest requires the anthropic SDK.\n"
            "  pip install anthropic\n"
            "See: skills/references/ingest-pdf.md"
        )
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return (
            "ANTHROPIC_API_KEY is not set.\n"
            "  Add it to .claude/settings.local.json → env, or export it in your shell.\n"
            "See: skills/references/ingest-pdf.md"
        )
    if not shutil.which("pdftoppm"):
        return (
            "poppler (pdftoppm) not found on PATH.\n"
            "  macOS: brew install poppler\n"
            "See: skills/references/ingest-pdf.md"
        )
    return None


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def _page_to_base64(pdf_path: Path, page_num: int, dpi: int) -> str:
    """Convert a single PDF page (1-indexed) to a base64-encoded PNG."""
    from pdf2image import convert_from_path
    images = convert_from_path(
        str(pdf_path),
        first_page=page_num,
        last_page=page_num,
        dpi=dpi,
        fmt="png",
    )
    buf = io.BytesIO()
    images[0].save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def _transcribe_page(client: Any, b64_image: str, page_num: int, model: str) -> str:
    """Send a page image to Claude Vision and return the transcribed text."""
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": f"Page {page_num}. {_TRANSCRIPTION_PROMPT}",
                    },
                ],
            }
        ],
    )
    return response.content[0].text


def _vision_pdf_to_markdown(
    pdf_path: Path,
    *,
    dpi: int = DEFAULT_DPI,
    max_pages: int | None = None,
    model: str = DEFAULT_MODEL,
) -> tuple[str, int]:
    """Convert a PDF to markdown via Claude Vision. Returns (markdown, pages_processed)."""
    import anthropic
    from pdf2image import pdfinfo_from_path

    info = pdfinfo_from_path(str(pdf_path))
    total = info["Pages"]
    n = total if max_pages is None else min(total, max_pages)

    if max_pages is not None and max_pages < total:
        print(
            f"  Vision: processing {n} of {total} pages (--max-pages {max_pages}). "
            "Omit to process all pages.",
            file=sys.stderr,
        )
    else:
        print(f"  Vision: processing {n} page(s) at {dpi} DPI…", file=sys.stderr)

    est_cost = n * 0.02
    print(f"  Estimated cost: ~${est_cost:.2f} ({n} pages × ~$0.02)", file=sys.stderr)

    client = anthropic.Anthropic()
    parts: list[str] = []

    for i in range(1, n + 1):
        if i == 1 or i % 10 == 0 or i == n:
            print(f"  Vision page {i}/{n}…", file=sys.stderr)
        b64 = _page_to_base64(pdf_path, i, dpi)
        text = _transcribe_page(client, b64, i, model)
        parts.append(f"## Page {i}\n\n{text}")

    if not parts:
        raise SystemExit("Vision produced no output.")

    return "\n\n".join(parts), n


# ---------------------------------------------------------------------------
# CLI + Adapter
# ---------------------------------------------------------------------------

def _arg_parser() -> ArgumentParser:
    p = ArgumentParser(prog="llm-wiki ingest pdf")
    p.add_argument("path", type=Path, help="Path to the PDF file")
    p.add_argument("--out", type=Path, help="Output path relative to raw/")
    p.add_argument("--dpi", type=int, default=DEFAULT_DPI, help=f"Image resolution per page (default: {DEFAULT_DPI})")
    p.add_argument("--max-pages", type=int, default=None, metavar="N", help="Cap page count (cost control)")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model ID (default: {DEFAULT_MODEL})")
    return p


class PdfVisionAdapter(Adapter):
    id: ClassVar[str] = "pdf"
    label: ClassVar[str] = "PDF → markdown via Claude Vision (Anthropic API)"

    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "api_key_env": "ANTHROPIC_API_KEY",
        "notes": (
            "Requires: pip install pdf2image anthropic; brew install poppler (macOS). "
            "See skills/references/ingest-pdf.md"
        ),
    }

    @classmethod
    def setup_checks(cls, cfg_slice: dict[str, Any]) -> list[str]:
        err = pdf_vision_preflight()
        return [err] if err else []

    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        ns = _arg_parser().parse_args(argv)

        err = pdf_vision_preflight()
        if err:
            raise SystemExit(err)

        path = ns.path.resolve()
        if not path.is_file():
            raise SystemExit(f"Not a file: {path}")

        # Cost threshold: if estimated cost > pdf.max_cost_usd, fallback to pdf-marker
        pdf_cfg = cfg.get("pdf", {})
        max_cost = pdf_cfg.get("max_cost_usd")
        if max_cost is not None:
            from pdf2image import pdfinfo_from_path
            info = pdfinfo_from_path(str(path))
            total = info["Pages"]
            n = total if ns.max_pages is None else min(total, ns.max_pages)
            est = n * 0.02
            if est > max_cost:
                print(
                    f"  [pdf] Estimated cost ${est:.2f} exceeds pdf.max_cost_usd=${max_cost:.2f}.\n"
                    f"  Falling back to pdf-marker (free Surya OCR).\n"
                    f"  To use Vision anyway, set pdf.max_cost_usd to null in config.json.",
                    file=sys.stderr,
                )
                from ingest.adapters.pdf_marker import PdfMarkerAdapter
                marker_argv = [str(ns.path)]
                if ns.out:
                    marker_argv += ["--out", str(ns.out)]
                if ns.max_pages:
                    marker_argv += ["--max-pages", str(ns.max_pages)]
                return PdfMarkerAdapter().run(vault, cfg, marker_argv)

        md, pages = _vision_pdf_to_markdown(
            path,
            dpi=ns.dpi,
            max_pages=ns.max_pages,
            model=ns.model,
        )

        out_rel = ns.out if ns.out else Path(f"{path.stem}.md")
        dest = raw_destination(vault, out_rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md, encoding="utf-8")

        commit_body = (
            f"Adapter: pdf-vision\n"
            f"Model: {ns.model}\n"
            f"DPI: {ns.dpi}\n"
            f"Pages: {pages}\n"
            f"Source: {path}"
        )

        return IngestResult(
            output_path=dest,
            message=f"Wrote {dest.relative_to(vault)} ({pages} pages via Claude Vision)",
            commit_body=commit_body,
        )
