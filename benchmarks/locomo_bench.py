"""LoCoMo benchmark runner (placeholder — wire dataset path when available)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def run_locomo(
    vault: Path,
    cfg: dict[str, Any],
    *,
    limit: int = 0,
    data_path: Path | None = None,
) -> dict[str, Any]:
    """
    LoCoMo multi-hop retrieval benchmark.

    Target (plan): 99%+ R@10 on 1,986 QA pairs. Full runner requires the
    official LoCoMo JSON layout; until then this records a stub entry and
    documents next steps in benchmarks/README.md.
    """
    if data_path is not None and data_path.is_file():
        try:
            with data_path.open(encoding="utf-8") as f:
                _ = json.load(f)
        except Exception as e:
            return {
                "summary": {
                    "suite": "locomo",
                    "status": "error",
                    "message": f"Could not read {data_path}: {e}",
                },
            }

    summary = {
        "suite": "locomo",
        "status": "pending",
        "questions": 0,
        "message": (
            "LoCoMo runner is not fully wired yet. "
            "Obtain the LoCoMo dataset (see benchmarks/README.md), "
            "then extend this module to convert conversations → vault + score R@10."
        ),
    }
    if limit:
        summary["limit_requested"] = limit

    return {"summary": summary}

