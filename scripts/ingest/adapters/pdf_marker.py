"""PDF ingest adapter using Marker (Surya OCR, free/local) via .venv-marker subprocess.

Marker's dependencies (marker-pdf) conflict with the main venv's anthropic/Pillow
versions. This adapter runs the conversion in an isolated .venv-marker subprocess,
keeping the main venv clean for Vision/Claude API use.

Install:
  python3 -m venv .venv-marker
  .venv-marker/bin/pip install marker-pdf

Optional LLM enhancement (--use-llm):
  Marker v1.10+ can use an LLM (Claude, Gemini, Ollama, OpenAI) alongside Surya OCR
  to merge tables, fix inline math, and correct OCR errors. Set API keys in the
  environment (e.g. ANTHROPIC_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY) — they are
  not passed on the Marker worker argv. Example:
    llm-wiki ingest pdf-marker file.pdf --use-llm
    GOOGLE_API_KEY=... llm-wiki ingest pdf-marker file.pdf --use-llm --llm-service gemini
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


def _subprocess_env() -> dict[str, str]:
    """Build subprocess environment with MPS fallback; inherits caller env for API keys."""
    env = os.environ.copy()
    # Prevent MPS index-out-of-bounds crash on macOS for large/high-res scans
    env.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    return env


def _apply_deprecated_llm_cli_keys_to_env(
    env: dict[str, str],
    *,
    claude_api_key: str | None,
    gemini_api_key: str | None,
    openai_api_key: str | None,
) -> None:
    """Merge deprecated --*-api-key flags into env for the Marker worker (stderr warnings)."""
    if claude_api_key:
        print(
            "pdf-marker: --claude-api-key is deprecated; use ANTHROPIC_API_KEY "
            "(value is set in the subprocess environment only, not argv).",
            file=sys.stderr,
        )
        env["ANTHROPIC_API_KEY"] = claude_api_key
    if gemini_api_key:
        print(
            "pdf-marker: --gemini-api-key is deprecated; use GOOGLE_API_KEY or GEMINI_API_KEY.",
            file=sys.stderr,
        )
        env["GOOGLE_API_KEY"] = gemini_api_key
    if openai_api_key:
        print(
            "pdf-marker: --openai-api-key is deprecated; use OPENAI_API_KEY.",
            file=sys.stderr,
        )
        env["OPENAI_API_KEY"] = openai_api_key


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
    strip_existing_ocr: bool = False,
    use_llm: bool = False,
    llm_service: str | None = None,
    claude_api_key: str | None = None,
    gemini_api_key: str | None = None,
    ollama_model: str | None = None,
    openai_api_key: str | None = None,
    openai_model: str | None = None,
    block_correction_prompt: str | None = None,
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
    if strip_existing_ocr:
        cmd.append("--strip-existing-ocr")
    if use_llm:
        cmd.append("--use-llm")
        if llm_service:
            cmd += ["--llm-service", llm_service]
        if ollama_model:
            cmd += ["--ollama-model", ollama_model]
        if openai_model:
            cmd += ["--openai-model", openai_model]

    env = _subprocess_env()
    if use_llm:
        _apply_deprecated_llm_cli_keys_to_env(
            env,
            claude_api_key=claude_api_key,
            gemini_api_key=gemini_api_key,
            openai_api_key=openai_api_key,
        )
        if block_correction_prompt:
            env["LLM_WIKI_MARKER_BLOCK_PROMPT"] = block_correction_prompt

    result = subprocess.run(
        cmd,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)

    if result.returncode != 0:
        tmp_path.unlink(missing_ok=True)
        raise SystemExit(f"Marker worker failed (exit {result.returncode})")

    text = tmp_path.read_text(encoding="utf-8")
    tmp_path.unlink(missing_ok=True)

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
    p = ArgumentParser(
        prog="llm-wiki ingest pdf-marker",
        description="Convert a PDF to markdown using Marker/Surya OCR (free, local).",
    )
    p.add_argument("path", type=Path, help="Path to the PDF file")
    p.add_argument("--out", type=Path, help="Output path relative to raw/")
    p.add_argument(
        "--max-pages", type=int, default=None, metavar="N",
        help="Process at most N pages",
    )
    p.add_argument(
        "--no-force-ocr", action="store_true",
        help="Skip --force_ocr (let Marker decide per page)",
    )
    p.add_argument(
        "--strip-existing-ocr", action="store_true",
        help="Remove existing OCR text and re-OCR with Surya (useful for bad embedded text)",
    )
    # LLM enhancement (Marker v1.10+)
    p.add_argument(
        "--use-llm", action="store_true",
        help=(
            "Use an LLM alongside Surya to merge tables, fix inline math, and correct "
            "OCR errors. Significantly improves accuracy on complex layouts."
        ),
    )
    p.add_argument(
        "--llm-service", default=None,
        choices=["claude", "gemini", "ollama", "openai"],
        help="LLM backend for --use-llm (default: claude if ANTHROPIC_API_KEY is set)",
    )
    p.add_argument(
        "--claude-api-key",
        default=None,
        help="Deprecated: set ANTHROPIC_API_KEY instead (injected into subprocess env only).",
    )
    p.add_argument(
        "--gemini-api-key",
        default=None,
        help="Deprecated: set GOOGLE_API_KEY or GEMINI_API_KEY instead (injected into env only).",
    )
    p.add_argument("--ollama-model", default=None, help="Ollama model name")
    p.add_argument(
        "--openai-api-key",
        default=None,
        help="Deprecated: set OPENAI_API_KEY instead (injected into subprocess env only).",
    )
    p.add_argument("--openai-model", default=None, help="OpenAI model name")
    p.add_argument(
        "--block-correction-prompt",
        default=None,
        metavar="PROMPT",
        help="Custom LLM prompt for output correction (requires --use-llm); passed via env, not argv.",
    )
    return p


class PdfMarkerAdapter(Adapter):
    id: ClassVar[str] = "pdf-marker"
    label: ClassVar[str] = "PDF → markdown via Marker/Surya OCR (free, local; optional LLM boost)"

    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "notes": (
            "Requires: python3 -m venv .venv-marker && .venv-marker/bin/pip install marker-pdf. "
            "Downloads ~1.5GB model weights on first run. No API key needed for basic OCR. "
            "Pass --use-llm to enable LLM-enhanced accuracy (Claude by default). "
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

        # Resolve default LLM service: prefer claude if key is available
        llm_service = ns.llm_service
        if ns.use_llm and not llm_service:
            if ns.claude_api_key or os.environ.get("ANTHROPIC_API_KEY"):
                llm_service = "claude"
            elif os.environ.get("GOOGLE_API_KEY"):
                llm_service = "gemini"

        md, pages = _marker_pdf_to_markdown(
            path,
            max_pages=ns.max_pages,
            force_ocr=not ns.no_force_ocr,
            strip_existing_ocr=ns.strip_existing_ocr,
            use_llm=ns.use_llm,
            llm_service=llm_service,
            claude_api_key=ns.claude_api_key,
            gemini_api_key=ns.gemini_api_key,
            ollama_model=ns.ollama_model,
            openai_api_key=ns.openai_api_key,
            openai_model=ns.openai_model,
            block_correction_prompt=ns.block_correction_prompt,
        )

        out_rel = ns.out if ns.out else Path(f"{path.stem}.md")
        dest = raw_destination(vault, out_rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md, encoding="utf-8")

        llm_note = f", LLM={llm_service}" if ns.use_llm else ""
        commit_body = (
            f"Adapter: pdf-marker (Surya OCR, .venv-marker subprocess)\n"
            f"Force OCR: {not ns.no_force_ocr}\n"
            f"Strip existing OCR: {ns.strip_existing_ocr}\n"
            f"LLM boost: {ns.use_llm}{f' ({llm_service})' if ns.use_llm else ''}\n"
            f"Pages: {pages}\n"
            f"Source: {path}"
        )

        return IngestResult(
            output_path=dest,
            message=f"Wrote {dest.relative_to(vault)} ({pages} pages via Marker/Surya{llm_note})",
            commit_body=commit_body,
        )
