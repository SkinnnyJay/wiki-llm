#!/usr/bin/env python3
"""Marker PDF worker — run via .venv-marker/bin/python, NOT via main venv.

This script is invoked as a subprocess by pdf_marker.py to isolate Marker's
dependencies (marker-pdf pins older anthropic/Pillow) from the main venv.

Usage (internal — called by pdf_marker.py):
  .venv-marker/bin/python _marker_subprocess.py <pdf_path> \\
    --out <output.md> [--max-pages N] [--no-force-ocr]
    [--use-llm] [--llm-service claude|gemini|ollama|openai]
    [--ollama-model MODEL] [--strip-existing-ocr]

API keys for LLM modes are read from the environment (e.g. ANTHROPIC_API_KEY, GOOGLE_API_KEY,
OPENAI_API_KEY) — never passed on the worker command line.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _build_config(args: argparse.Namespace) -> dict:
    cfg: dict = {
        "output_format": "markdown",
        "force_ocr": not args.no_force_ocr,
        "disable_image_extraction": True,
    }
    if args.max_pages is not None:
        # ConfigParser.generate_config_dict() calls parse_range_str() which expects a string
        cfg["page_range"] = f"0-{args.max_pages - 1}"
    if args.strip_existing_ocr:
        cfg["strip_existing_ocr"] = True
    return cfg


def _build_converter(args: argparse.Namespace):
    from marker.config.parser import ConfigParser
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict

    base_cfg = _build_config(args)

    if args.use_llm:
        svc = args.llm_service or "claude"
        if svc == "claude":
            base_cfg["llm_service"] = "marker.services.claude.ClaudeService"
            if os.environ.get("ANTHROPIC_API_KEY"):
                base_cfg["claude_api_key"] = os.environ["ANTHROPIC_API_KEY"]
        elif svc == "gemini":
            base_cfg["llm_service"] = "marker.services.gemini.GoogleGeminiService"
            gk = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            if gk:
                base_cfg["gemini_api_key"] = gk
        elif svc == "ollama":
            base_cfg["llm_service"] = "marker.services.ollama.OllamaService"
            if args.ollama_model:
                base_cfg["ollama_model"] = args.ollama_model
        elif svc == "openai":
            base_cfg["llm_service"] = "marker.services.openai.OpenAIService"
            if os.environ.get("OPENAI_API_KEY"):
                base_cfg["openai_api_key"] = os.environ["OPENAI_API_KEY"]
            if args.openai_model:
                base_cfg["openai_model"] = args.openai_model

        bp = os.environ.get("LLM_WIKI_MARKER_BLOCK_PROMPT")
        if bp:
            base_cfg["block_correction_prompt"] = bp

    config_parser = ConfigParser(base_cfg)
    print("  Marker: loading models (first run downloads ~1.5GB)…", file=sys.stderr, flush=True)
    return PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service() if args.use_llm else None,
    )


def main() -> int:
    p = argparse.ArgumentParser(prog="_marker_subprocess")
    p.add_argument("pdf_path", type=Path)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--max-pages", type=int, default=None)
    p.add_argument("--no-force-ocr", action="store_true")
    p.add_argument("--strip-existing-ocr", action="store_true",
                   help="Remove existing OCR text and re-OCR with Surya")
    # LLM enhancement
    p.add_argument("--use-llm", action="store_true",
                   help="Use an LLM to improve accuracy (merges tables, fixes inline math, etc.)")
    p.add_argument("--llm-service", default=None,
                   choices=["claude", "gemini", "ollama", "openai"],
                   help="LLM backend to use with --use-llm (default: claude)")
    p.add_argument("--ollama-model", default=None)
    p.add_argument("--openai-model", default=None)
    args = p.parse_args()

    from marker.output import text_from_rendered

    if args.use_llm:
        svc_name = args.llm_service or "claude"
        print(f"  Marker: LLM mode enabled (service: {svc_name})", file=sys.stderr, flush=True)

    converter = _build_converter(args)
    print(f"  Marker: converting {args.pdf_path.name}…", file=sys.stderr, flush=True)
    rendered = converter(str(args.pdf_path))
    text, _, _ = text_from_rendered(rendered)

    # Use metadata page count when available, fall back to header heuristic
    pages = 0
    if hasattr(rendered, "metadata") and rendered.metadata:
        meta = rendered.metadata
        if isinstance(meta, dict):
            page_stats = meta.get("page_stats", [])
            if page_stats:
                pages = len(page_stats)
    if pages == 0:
        pages = text.count("\n## ") or args.max_pages or 0

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)

    print(f"__PAGES__:{pages}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
