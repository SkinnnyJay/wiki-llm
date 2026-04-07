#!/usr/bin/env python3
"""Marker PDF worker — run via .venv-marker/bin/python, NOT via main venv.

This script is invoked as a subprocess by pdf_marker.py to isolate Marker's
dependencies (marker-pdf pins older anthropic/Pillow) from the main venv.

Usage (internal — called by pdf_marker.py):
  .venv-marker/bin/python _marker_subprocess.py <pdf_path> \\
    --out <output.md> [--max-pages N] [--no-force-ocr]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(prog="_marker_subprocess")
    p.add_argument("pdf_path", type=Path)
    p.add_argument("--out", type=Path, default=None, help="Write markdown here (else stdout)")
    p.add_argument("--max-pages", type=int, default=None)
    p.add_argument("--no-force-ocr", action="store_true")
    args = p.parse_args()

    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered

    config: dict = {
        "output_format": "markdown",
        "force_ocr": not args.no_force_ocr,
        "disable_image_extraction": True,
    }
    if args.max_pages is not None:
        config["page_range"] = list(range(args.max_pages))

    print("  Marker: loading models (first run downloads ~1.5GB)…", file=sys.stderr, flush=True)
    converter = PdfConverter(artifact_dict=create_model_dict(), config=config)

    print(f"  Marker: converting {args.pdf_path.name}…", file=sys.stderr, flush=True)
    rendered = converter(str(args.pdf_path))
    text, _, _ = text_from_rendered(rendered)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)

    pages = text.count("\n## ") or args.max_pages or 0
    # Signal page count to parent process via stderr tag
    print(f"__PAGES__:{pages}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
