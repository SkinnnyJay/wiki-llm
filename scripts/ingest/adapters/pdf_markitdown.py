"""PDF ingest adapter using Microsoft MarkItDown (lightweight, MIT, no ML models).

MarkItDown uses pdfminer.six for text extraction from digital PDFs. It is extremely
fast and has zero additional dependencies beyond what is already in the main venv, but
it does NOT run OCR — it only extracts text that is already embedded in the PDF.

Best for:
  - Digital/born-digital PDFs with embedded text
  - Office documents (Word, Excel, PowerPoint) also supported via `markitdown[all]`
  - Quick bulk processing where speed matters more than perfection

Not good for:
  - Scanned PDFs (no embedded text) — use pdf-vision or pdf-marker instead
  - Complex table layouts — use pdf-vision or pdf-marker instead

Install (already included in main venv):
  pip install 'markitdown[pdf]'

Optional LLM image description (for PDFs with embedded images):
  pip install openai  # or anthropic via the markitdown-ocr plugin
  See: https://github.com/microsoft/markitdown
"""
from __future__ import annotations

import os
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, ClassVar

from lib.paths import raw_destination
from ingest.base import Adapter, IngestResult


# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

def pdf_markitdown_preflight() -> str | None:
    """Return an error message if markitdown or pdfminer is not installed."""
    try:
        import markitdown  # noqa: F401
    except ImportError:
        return (
            "MarkItDown is not installed.\n"
            "  pip install 'markitdown[pdf]'\n"
            "See: https://github.com/microsoft/markitdown"
        )
    try:
        import pdfminer  # noqa: F401
    except ImportError:
        return (
            "pdfminer.six is not installed (required for PDF support).\n"
            "  pip install 'markitdown[pdf]'\n"
            "See: https://github.com/microsoft/markitdown"
        )
    return None


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def _markitdown_pdf_to_markdown(
    pdf_path: Path,
    *,
    llm_client: Any = None,
    llm_model: str | None = None,
    llm_prompt: str | None = None,
) -> tuple[str, int]:
    """Convert PDF to markdown via MarkItDown. Returns (text, pages)."""
    from markitdown import MarkItDown

    kwargs: dict[str, Any] = {}
    if llm_client is not None:
        kwargs["llm_client"] = llm_client
        if llm_model:
            kwargs["llm_model"] = llm_model
        if llm_prompt:
            kwargs["llm_prompt"] = llm_prompt

    md = MarkItDown(enable_plugins=False, **kwargs)
    result = md.convert(str(pdf_path))
    text = result.text_content

    # Estimate pages — MarkItDown does not expose a page count
    # Use form-feed characters (common in pdfminer output) or fall back to 0
    pages = text.count("\f") or text.count("<!-- Page") or 0

    return text, pages


def _build_llm_client(llm_service: str | None, api_key: str | None) -> Any:
    """Build an LLM client for MarkItDown image descriptions."""
    svc = llm_service or "openai"
    if svc == "openai":
        try:
            from openai import OpenAI
            return OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        except ImportError:
            return None
    if svc == "anthropic":
        try:
            import anthropic
            return anthropic.Anthropic(
                api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
            )
        except ImportError:
            return None
    return None


# ---------------------------------------------------------------------------
# CLI + Adapter
# ---------------------------------------------------------------------------

def _arg_parser() -> ArgumentParser:
    p = ArgumentParser(
        prog="llm-wiki ingest pdf-markitdown",
        description=(
            "Convert a PDF to markdown using Microsoft MarkItDown (fast, no ML, "
            "best for digital PDFs with embedded text)."
        ),
    )
    p.add_argument("path", type=Path, help="Path to the PDF file")
    p.add_argument("--out", type=Path, help="Output path relative to raw/")
    # LLM image descriptions (optional)
    p.add_argument(
        "--llm-service", default=None, choices=["openai", "anthropic"],
        help="LLM service for image descriptions in the PDF (optional)",
    )
    p.add_argument("--llm-model", default=None, help="LLM model name for image descriptions")
    p.add_argument("--api-key", default=None, help="API key for the LLM service")
    p.add_argument(
        "--llm-prompt", default=None,
        help="Custom prompt for LLM image descriptions",
    )
    return p


class PdfMarkitdownAdapter(Adapter):
    id: ClassVar[str] = "pdf-markitdown"
    label: ClassVar[str] = (
        "PDF → markdown via MarkItDown (Microsoft, MIT, fast, digital PDFs only)"
    )

    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "notes": (
            "Requires: pip install 'markitdown[pdf]' (already in main venv). "
            "Extracts embedded text only — no OCR. Best for born-digital PDFs. "
            "See: https://github.com/microsoft/markitdown"
        ),
    }

    @classmethod
    def setup_checks(cls, cfg_slice: dict[str, Any]) -> list[str]:
        err = pdf_markitdown_preflight()
        return [err] if err else []

    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        ns = _arg_parser().parse_args(argv)

        err = pdf_markitdown_preflight()
        if err:
            raise SystemExit(err)

        path = ns.path.resolve()
        if not path.is_file():
            raise SystemExit(f"Not a file: {path}")

        llm_client = None
        if ns.llm_service:
            llm_client = _build_llm_client(ns.llm_service, ns.api_key)
            if llm_client is None:
                raise SystemExit(
                    f"Could not build LLM client for service '{ns.llm_service}'. "
                    "Check the SDK is installed and the API key is set."
                )

        md, pages = _markitdown_pdf_to_markdown(
            path,
            llm_client=llm_client,
            llm_model=ns.llm_model,
            llm_prompt=ns.llm_prompt,
        )

        out_rel = ns.out if ns.out else Path(f"{path.stem}.md")
        dest = raw_destination(vault, out_rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md, encoding="utf-8")

        llm_note = f", LLM={ns.llm_service}/{ns.llm_model}" if ns.llm_service else ""
        commit_body = (
            f"Adapter: pdf-markitdown (Microsoft MarkItDown v{_markitdown_version()})\n"
            f"LLM image descriptions: {bool(ns.llm_service)}{llm_note}\n"
            f"Pages: {pages or 'unknown'}\n"
            f"Source: {path}"
        )

        pages_str = str(pages) if pages else "unknown pages"
        return IngestResult(
            output_path=dest,
            message=f"Wrote {dest.relative_to(vault)} ({pages_str} via MarkItDown{llm_note})",
            commit_body=commit_body,
        )


def _markitdown_version() -> str:
    try:
        import markitdown
        return getattr(markitdown, "__version__", "?")
    except ImportError:
        return "?"
