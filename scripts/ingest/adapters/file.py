from __future__ import annotations

import shutil
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, ClassVar

from lib.paths import raw_destination

from ingest.base import Adapter, IngestResult


class FileAdapter(Adapter):
    id: ClassVar[str] = "file"
    label: ClassVar[str] = "Copy or read local file into raw/"
    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "integration_keys": [],
        "notes": "No API keys; enable in integrations.file if you use per-adapter gating.",
    }

    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        p = ArgumentParser(prog="llm-wiki ingest file")
        p.add_argument("path", type=Path)
        p.add_argument("--out", type=Path, help="Relative path under raw/")
        ns = p.parse_args(argv)
        src = ns.path.resolve()
        if not src.is_file():
            raise SystemExit(f"Not a file: {src}")
        if ns.out:
            dest = raw_destination(vault, ns.out)
        else:
            dest = raw_destination(vault, Path(src.name))
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return IngestResult(dest, f"Copied to {dest.relative_to(vault)}")
