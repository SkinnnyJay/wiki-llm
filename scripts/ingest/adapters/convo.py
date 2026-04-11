"""Ingest chat transcripts: normalize to exchange-pair markdown in raw/."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import Any, ClassVar

from lib.convo_miner import process_convo_file
from lib.paths import raw_destination
from ingest.base import Adapter, IngestResult


class ConvoAdapter(Adapter):
    id: ClassVar[str] = "convo"
    label: ClassVar[str] = "Normalize chat export / transcript to markdown (exchange pairs)"
    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "integration_keys": [],
        "notes": "Enable integrations.convo in config.json to use.",
    }

    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        p = ArgumentParser(prog="llm-wiki ingest convo")
        p.add_argument("path", type=Path, help="Transcript .txt, .md, or .jsonl")
        p.add_argument("--out", type=Path, help="Relative path under raw/ (default: stem.md)")
        ns = p.parse_args(argv)
        src = ns.path.resolve()
        if not src.is_file():
            raise SystemExit(f"Not a file: {src}")
        md = process_convo_file(src)
        out = ns.out if ns.out else Path(f"{src.stem}.md")
        dest = raw_destination(vault, out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md, encoding="utf-8")
        return IngestResult(dest, f"Wrote normalized transcript to {dest.relative_to(vault)}")
