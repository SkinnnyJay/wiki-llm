"""PDF ingest adapter using Marker (Surya OCR, free/local) via .venv-marker subprocess.

Marker's dependencies (marker-pdf) conflict with the main venv's anthropic/Pillow
versions. This adapter runs the conversion in an isolated .venv-marker subprocess,
keeping the main venv clean for Vision/Claude API use.

Install:
  python3 -m venv .venv-marker
  .venv-marker/bin/pip install marker-pdf
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, ClassVar

from lib.paths import raw_destination
from ingest.base import Adapter, IngestResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root() -> Path | None:
    here = Path(__file__).resolve()
    for d in [here, *here.parents]:
        if (d / "scripts" / "llm_wiki.py").is_file():
            return d
    return None


def _marker_python() -> Path | None:
    repo = _repo_root()
    if repo is None:
        return None
    for name in ("python3", "python"):
        p = repo / ".venv-marker" / "bin" / name
        if p.is_file():
            return p
    return None


def _worker_script() -> Path:
    return Path(__file__).resolve().parent / "_marker_subprocess.py"


# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

def pdf_marker_preflight() -> str | None:
    """Return an error message if .venv-marker is missing or marker-pdf not installed."""
    python = _marker_python()
    if python is None:
        return (
            "PDF Marker requires a dedicated virtual environment at .venv-marker/.\n"
            "  python3 -m venv .venv-marker\n"
            "  .venv-marker/bin/pip install marker-pdf\n"
            "Note: first run downloads ~1.5GB of Surya model weights.\n"
            "See: skills/references/ingest-pdf-marker.md"
        )
    # Use find_spec — fast path lookup, no model loading
    result = subprocess.run(
        [str(python), "-c",
         "import importlib.util, sys; "
         "s = importlib.util.find_spec('marker'); "
         "sys.exit(0 if s else 1)"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return (
            ".venv-marker exists but marker-pdf is not installed.\n"
            "  .venv-marker/bin/pip install marker-pdf\n"
            "See: skills/references/ingest-pdf-marker.md"
        )
    return None


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def _marker_pdf_to_markdown(
    pdf_path: Path,
    *,
    max_pages: int | None = None,
    force_ocr: bool = True,
) -> tuple[str, int]:
    """Convert PDF to markdown via .venv-marker subprocess. Returns (text, pages)."""
    python = _marker_python()
    if python is None:
        raise SystemExit("pdf-marker: .venv-marker not found. Run preflight check.")

    worker = _worker_script()
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    cmd = [str(python), str(worker), str(pdf_path), "--out", str(tmp_path)]
    if max_pages is not None:
        cmd += ["--max-pages", str(max_pages)]
    if not force_ocr:
        cmd.append("--no-force-ocr")

    # Let stdout/stderr flow to terminal so user sees Marker's progress
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    # Echo stderr to terminal (progress messages)
    if result.stderr:
        import sys
        print(result.stderr, end="", file=sys.stderr, flush=True)

    if result.returncode != 0:
        tmp_path.unlink(missing_ok=True)
        raise SystemExit(f"Marker worker failed (exit {result.returncode})")

    text = tmp_path.read_text(encoding="utf-8")
    tmp_path.unlink(missing_ok=True)

    # Parse page count from stderr tag or count headers
    pages = 0
    if result.stderr:
        m = re.search(r"__PAGES__:(\d+)", result.stderr)
        if m:
            pages = int(m.group(1))
    if pages == 0:
        pages = text.count("\n## ") or max_pages or 0

    return text, pages


# ---------------------------------------------------------------------------
# CLI + Adapter
# ---------------------------------------------------------------------------

def _arg_parser() -> ArgumentParser:
    p = ArgumentParser(prog="llm-wiki ingest pdf-marker")
    p.add_argument("path", type=Path, help="Path to the PDF file")
    p.add_argument("--out", type=Path, help="Output path relative to raw/")
    p.add_argument(
        "--max-pages", type=int, default=None, metavar="N",
        help="Process at most N pages (0-indexed page range)",
    )
    p.add_argument(
        "--no-force-ocr", action="store_true",
        help="Skip --force_ocr (let Marker decide per page)",
    )
    return p


class PdfMarkerAdapter(Adapter):
    id: ClassVar[str] = "pdf-marker"
    label: ClassVar[str] = "PDF → markdown via Marker/Surya OCR (free, local, no API key)"

    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "notes": (
            "Requires: python3 -m venv .venv-marker && .venv-marker/bin/pip install marker-pdf. "
            "Downloads ~1.5GB model weights on first run. No API key needed. "
            "See skills/references/ingest-pdf-marker.md"
        ),
    }

    @classmethod
    def setup_checks(cls, cfg_slice: dict[str, Any]) -> list[str]:
        err = pdf_marker_preflight()
        return [err] if err else []

    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        ns = _arg_parser().parse_args(argv)

        err = pdf_marker_preflight()
        if err:
            raise SystemExit(err)

        path = ns.path.resolve()
        if not path.is_file():
            raise SystemExit(f"Not a file: {path}")

        md, pages = _marker_pdf_to_markdown(
            path,
            max_pages=ns.max_pages,
            force_ocr=not ns.no_force_ocr,
        )

        out_rel = ns.out if ns.out else Path(f"{path.stem}.md")
        dest = raw_destination(vault, out_rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md, encoding="utf-8")

        commit_body = (
            f"Adapter: pdf-marker (Surya OCR, .venv-marker subprocess)\n"
            f"Force OCR: {not ns.no_force_ocr}\n"
            f"Pages: {pages}\n"
            f"Source: {path}"
        )

        return IngestResult(
            output_path=dest,
            message=f"Wrote {dest.relative_to(vault)} ({pages} pages via Marker/Surya)",
            commit_body=commit_body,
        )
