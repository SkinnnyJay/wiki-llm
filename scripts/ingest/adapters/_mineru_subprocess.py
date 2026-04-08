#!/usr/bin/env python3
"""MinerU PDF worker — run via .venv-mineru/bin/python, NOT via main venv.

MinerU's dependencies (torch, paddleocr, heavy ML stack) conflict with the main venv.
This script is invoked as a subprocess by pdf_mineru.py to isolate those deps.

Usage (internal — called by pdf_mineru.py):
  .venv-mineru/bin/python _mineru_subprocess.py <pdf_path> \\
    --out <output.md> [--max-pages N] [--backend pipeline|vlm|hybrid]
    [--lang <code>]
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import tempfile
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(prog="_mineru_subprocess")
    p.add_argument("pdf_path", type=Path)
    p.add_argument("--out", type=Path, default=None,
                   help="Write final markdown here")
    p.add_argument("--max-pages", type=int, default=None,
                   help="Process at most N pages (0-indexed end page)")
    p.add_argument(
        "--backend", default="pipeline",
        choices=["pipeline", "vlm", "hybrid"],
        help="MinerU inference backend (default: pipeline — pure CPU compatible)",
    )
    p.add_argument("--lang", default=None,
                   help="OCR language hint (e.g. 'en', 'ch'). Leave unset for auto.")
    args = p.parse_args()

    # MinerU CLI writes a directory tree; use a temp dir to collect output
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd_parts = [
            sys.executable, "-m", "mineru.cli.main",
            "-p", str(args.pdf_path),
            "-o", tmpdir,
            "-b", args.backend,
        ]
        if args.max_pages is not None:
            # MinerU uses 0-indexed end_page (exclusive upper bound)
            cmd_parts += ["--end-page", str(args.max_pages - 1)]
        if args.lang:
            cmd_parts += ["--lang", args.lang]

        import subprocess
        print(f"  MinerU: converting {args.pdf_path.name} (backend={args.backend})…",
              file=sys.stderr, flush=True)
        result = subprocess.run(cmd_parts, capture_output=False, text=True)
        if result.returncode != 0:
            print(f"  MinerU CLI failed (exit {result.returncode})", file=sys.stderr)
            sys.exit(result.returncode)

        # Find the generated .md file — MinerU outputs to tmpdir/<stem>/<stem>.md
        md_files = glob.glob(os.path.join(tmpdir, "**", "*.md"), recursive=True)
        # Exclude auto_layout and other debug files
        md_files = [f for f in md_files if not os.path.basename(f).startswith("_")]
        if not md_files:
            print("  MinerU: no .md output found in output directory", file=sys.stderr)
            sys.exit(1)

        # Pick the largest .md (main content, not a sidecar)
        md_path = max(md_files, key=lambda f: os.path.getsize(f))
        text = Path(md_path).read_text(encoding="utf-8")

        # Count pages from MinerU's page separators or header heuristic
        pages = text.count("\n\n---\n\n") + 1 if "\n\n---\n\n" in text else 0
        if pages <= 1:
            pages = text.count("\n## ") or args.max_pages or 0
        print(f"__PAGES__:{pages}", file=sys.stderr, flush=True)

        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
