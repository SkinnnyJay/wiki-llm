"""ConvoMem-style benchmark — accepts LME-shaped JSON for retrieval scoring."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def run_convomem(
    vault: Path,
    cfg: dict[str, Any],
    *,
    limit: int = 0,
    data_path: Path | None = None,
) -> dict[str, Any]:
    """
    Run retrieval when ``data_path`` points to a JSON array of LME-shaped entries
    (``haystack_sessions``, ``haystack_session_ids``, ``haystack_dates``,
    ``question``, ``answer_session_ids``).

    Full Salesforce/ConvoMem HF layouts are not auto-downloaded (multi-GB);
    convert or subset to this shape offline. See benchmarks/README.md.
    """
    from benchmarks.lme_bench import complete_lme_derived_suite, run_lme

    if data_path is None or not data_path.is_file():
        return {
            "summary": {
                "suite": "convomem",
                "status": "pending",
                "questions": 0,
                "message": (
                    "Pass --data /path/to/lme-shaped.json (array of haystack+question rows). "
                    "See benchmarks/README.md for ConvoMem dataset pointers."
                ),
            },
        }

    try:
        with data_path.open(encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        return {
            "summary": {
                "suite": "convomem",
                "status": "error",
                "message": str(e),
            },
        }

    if not isinstance(raw, list) or not raw:
        return {
            "summary": {
                "suite": "convomem",
                "status": "error",
                "message": "Expected a non-empty JSON array",
            },
        }

    first = raw[0]
    if not isinstance(first, dict) or "haystack_sessions" not in first:
        return {
            "summary": {
                "suite": "convomem",
                "status": "error",
                "message": (
                    "Each item must include haystack_sessions, haystack_session_ids, "
                    "haystack_dates, question, answer_session_ids"
                ),
            },
        }

    entries = raw
    if limit > 0:
        entries = entries[:limit]

    bcfg = cfg.get("benchmark") or {}
    backend = (bcfg.get("search") or {}).get("backend", "fts5")
    comp = bcfg.get("compress_method", "raw")

    result = run_lme(
        entries,
        vault,
        cfg,
        backend=backend,
        compressor_name=comp,
        limit=0,
        top_k=5,
    )
    return complete_lme_derived_suite(
        vault,
        cfg,
        result,
        suite="convomem",
        backend=backend,
        compressor=comp,
        entry_count=len(entries),
    )
