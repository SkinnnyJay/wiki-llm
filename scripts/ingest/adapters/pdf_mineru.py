"""PDF ingest adapter using MinerU (OpenDataLab, AGPL-3.0, high accuracy).

MinerU is a high-accuracy document parsing engine with VLM+OCR dual engine,
LaTeX formula extraction, HTML table output, 109-language OCR, and cross-page
table merging. It rivals commercial tools like LlamaParse and Mathpix.

MinerU's heavy ML stack (torch, paddleocr, heavy vision models) conflicts with
the main venv, so this adapter runs conversion in an isolated .venv-mineru
subprocess — the same isolation pattern used by pdf-marker.

Backends:
  pipeline  — Fast, stable, CPU or GPU, 86+ OmniDocBench score (default)
  vlm       — Highest accuracy (90+), requires 8GB+ GPU
  hybrid    — Balanced, native text extraction + OCR

Install:
  python3 -m venv .venv-mineru
  .venv-mineru/bin/pip install uv
  .venv-mineru/bin/uv pip install "mineru[all]"

Note: first run downloads model weights (~2-4GB depending on backend).
See: https://github.com/opendatalab/MinerU
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
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


def _mineru_python() -> Path | None:
    repo = _repo_root()
    if repo is None:
        return None
    for name in ("python3", "python"):
        p = repo / ".venv-mineru" / "bin" / name
        if p.is_file():
            return p
    return None


def _worker_script() -> Path:
    return Path(__file__).resolve().parent / "_mineru_subprocess.py"


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    return env


# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

def pdf_mineru_preflight() -> str | None:
    """Return an error message if .venv-mineru is missing or mineru not installed."""
    python = _mineru_python()
    if python is None:
        return (
            "MinerU requires a dedicated virtual environment at .venv-mineru/.\n"
            "  python3 -m venv .venv-mineru\n"
            "  .venv-mineru/bin/pip install uv\n"
            "  .venv-mineru/bin/uv pip install 'mineru[all]'\n"
            "Note: first run downloads ~2-4GB of model weights.\n"
            "See: https://github.com/opendatalab/MinerU"
        )
    result = subprocess.run(
        [str(python), "-c",
         "import importlib.util, sys; "
         "s = importlib.util.find_spec('mineru'); "
         "sys.exit(0 if s else 1)"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return (
            ".venv-mineru exists but mineru is not installed.\n"
            "  .venv-mineru/bin/pip install uv\n"
            "  .venv-mineru/bin/uv pip install 'mineru[all]'\n"
            "See: https://github.com/opendatalab/MinerU"
        )
    return None


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def _mineru_pdf_to_markdown(
    pdf_path: Path,
    *,
    max_pages: int | None = None,
    backend: str = "pipeline",
    lang: str | None = None,
) -> tuple[str, int]:
    """Convert PDF to markdown via .venv-mineru subprocess. Returns (text, pages)."""
    python = _mineru_python()
    if python is None:
        raise SystemExit("pdf-mineru: .venv-mineru not found. Run preflight check.")

    worker = _worker_script()
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    cmd = [str(python), str(worker), str(pdf_path), "--out", str(tmp_path),
           "--backend", backend]
    if max_pages is not None:
        cmd += ["--max-pages", str(max_pages)]
    if lang:
        cmd += ["--lang", lang]

    result = subprocess.run(
        cmd,
        stderr=subprocess.PIPE,
        text=True,
        env=_subprocess_env(),
    )
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)

    if result.returncode != 0:
        tmp_path.unlink(missing_ok=True)
        raise SystemExit(f"MinerU worker failed (exit {result.returncode})")

    text = tmp_path.read_text(encoding="utf-8")
    tmp_path.unlink(missing_ok=True)

    pages = 0
    if result.stderr:
        m = re.search(r"__PAGES__:(\d+)", result.stderr)
        if m:
            pages = int(m.group(1))
    if pages == 0:
        pages = max_pages or 0

    return text, pages


# ---------------------------------------------------------------------------
# CLI + Adapter
# ---------------------------------------------------------------------------

def _arg_parser() -> ArgumentParser:
    p = ArgumentParser(
        prog="llm-wiki ingest pdf-mineru",
        description="Convert a PDF to markdown using MinerU (OpenDataLab, high accuracy).",
    )
    p.add_argument("path", type=Path, help="Path to the PDF file")
    p.add_argument("--out", type=Path, help="Output path relative to raw/")
    p.add_argument(
        "--max-pages", type=int, default=None, metavar="N",
        help="Process at most N pages",
    )
    p.add_argument(
        "--backend", default="pipeline",
        choices=["pipeline", "vlm", "hybrid"],
        help=(
            "MinerU inference backend: pipeline (CPU/GPU, default), "
            "vlm (highest accuracy, 8GB+ GPU required), "
            "hybrid (balanced)"
        ),
    )
    p.add_argument(
        "--lang", default=None, metavar="CODE",
        help="OCR language hint (e.g. 'en', 'ch', 'fr'). Auto-detected if not set.",
    )
    return p


class PdfMineruAdapter(Adapter):
    id: ClassVar[str] = "pdf-mineru"
    label: ClassVar[str] = (
        "PDF → markdown via MinerU (OpenDataLab, AGPL, VLM+OCR, LaTeX/HTML tables)"
    )

    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "notes": (
            "Requires: python3 -m venv .venv-mineru && "
            ".venv-mineru/bin/uv pip install 'mineru[all]'. "
            "Downloads ~2-4GB model weights on first run. No API key needed. "
            "See: https://github.com/opendatalab/MinerU"
        ),
    }

    @classmethod
    def setup_checks(cls, cfg_slice: dict[str, Any]) -> list[str]:
        err = pdf_mineru_preflight()
        return [err] if err else []

    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        ns = _arg_parser().parse_args(argv)

        err = pdf_mineru_preflight()
        if err:
            raise SystemExit(err)

        path = ns.path.resolve()
        if not path.is_file():
            raise SystemExit(f"Not a file: {path}")

        md, pages = _mineru_pdf_to_markdown(
            path,
            max_pages=ns.max_pages,
            backend=ns.backend,
            lang=ns.lang,
        )

        out_rel = ns.out if ns.out else Path(f"{path.stem}.md")
        dest = raw_destination(vault, out_rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md, encoding="utf-8")

        commit_body = (
            f"Adapter: pdf-mineru (MinerU, .venv-mineru subprocess)\n"
            f"Backend: {ns.backend}\n"
            f"Lang: {ns.lang or 'auto'}\n"
            f"Pages: {pages}\n"
            f"Source: {path}"
        )

        return IngestResult(
            output_path=dest,
            message=f"Wrote {dest.relative_to(vault)} ({pages} pages via MinerU/{ns.backend})",
            commit_body=commit_body,
        )
