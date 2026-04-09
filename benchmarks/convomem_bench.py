"""ConvoMem benchmark runner (placeholder — wire dataset path when available)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def run_convomem(
    vault: Path,
    cfg: dict[str, Any],
    *,
    limit: int = 0,
    data_path: Path | None = None,
) -> dict[str, Any]:
    """
    ConvoMem large-scale memory category benchmark.

    Target (plan): 99%+ average recall across 6 categories. Full runner
    requires the published ConvoMem QA format; extend this module once
    data is available locally.
    """
    if data_path is not None and data_path.is_file():
        try:
            with data_path.open(encoding="utf-8") as f:
                _ = json.load(f)
        except Exception as e:
            return {
                "summary": {
                    "suite": "convomem",
                    "status": "error",
                    "message": f"Could not read {data_path}: {e}",
                },
            }

    summary = {
        "suite": "convomem",
        "status": "pending",
        "questions": 0,
        "message": (
            "ConvoMem runner is not fully wired yet. "
            "See benchmarks/README.md for dataset pointers and "
            "how to map categories into the same vault + search harness as LME."
        ),
    }
    if limit:
        summary["limit_requested"] = limit

    return {"summary": summary}

