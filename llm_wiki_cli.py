"""Setuptools entry point for ``pip install`` — delegates to ``scripts/llm_wiki.py``."""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent / "scripts"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import llm_wiki  # noqa: PLC0415 — after path fixup

    return int(llm_wiki.main())


if __name__ == "__main__":
    raise SystemExit(main())
