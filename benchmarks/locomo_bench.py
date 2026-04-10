"""LoCoMo benchmark — snap-research/locomo locomo10.json → LME-style retrieval eval."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_LOCOMO_URL = (
    "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json"
)


def download_locomo(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / "locomo10.json"
    if dest.is_file() and dest.stat().st_size > 1000:
        return dest
    print(f"Downloading LoCoMo dataset to {dest} ...")
    req = urllib.request.Request(_LOCOMO_URL, method="GET")
    with urllib.request.urlopen(req, timeout=600) as resp:
        dest.write_bytes(resp.read())
    return dest


def _session_numbers(conv: dict[str, Any]) -> list[int]:
    nums: set[int] = set()
    for k in conv.keys():
        m = re.match(r"session_(\d+)$", k)
        if m:
            nums.add(int(m.group(1)))
    return sorted(nums)


def _turns_to_lme_session(
    turns: list[dict[str, Any]],
    *,
    speaker_a: str,
    speaker_b: str,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for t in turns:
        if not isinstance(t, dict) or "text" not in t:
            continue
        sp = str(t.get("speaker", ""))
        role = "user" if sp == speaker_a else "assistant"
        out.append({"role": role, "content": str(t.get("text", ""))})
    return out


def _evidence_to_gold_sids(evidence: list[Any]) -> set[str]:
    """Map LoCoMo evidence ids like D18:5 → session id S18."""
    gold: set[str] = set()
    for ev in evidence:
        if not isinstance(ev, str) or not ev.startswith("D"):
            continue
        head = ev.split(":", 1)[0]
        num = head[1:] if len(head) > 1 else ""
        if num.isdigit():
            gold.add(f"S{num}")
    return gold


def locomo_to_lme_entries(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert LoCoMo JSON array to LME-shaped entries for ``run_lme``."""
    entries: list[dict[str, Any]] = []
    for ci, item in enumerate(raw):
        conv = item.get("conversation") or {}
        speaker_a = str(conv.get("speaker_a", "SpeakerA"))
        speaker_b = str(conv.get("speaker_b", "SpeakerB"))
        nums = _session_numbers(conv)
        sessions: list[list[dict[str, str]]] = []
        session_ids: list[str] = []
        dates: list[str] = []
        for n in nums:
            key = f"session_{n}"
            turns = conv.get(key)
            if not isinstance(turns, list):
                continue
            sessions.append(_turns_to_lme_session(turns, speaker_a=speaker_a, speaker_b=speaker_b))
            session_ids.append(f"S{n}")
            dt = conv.get(f"session_{n}_date_time", "")
            dates.append(str(dt) if dt is not None else "")

        if not sessions:
            continue

        for qi, qa in enumerate(item.get("qa") or []):
            if not isinstance(qa, dict):
                continue
            q = qa.get("question")
            if not q:
                continue
            ev = qa.get("evidence") or []
            gold = _evidence_to_gold_sids(ev if isinstance(ev, list) else [])
            if not gold:
                continue
            qid = f"locomo_c{ci}_q{qi}"
            entries.append(
                {
                    "haystack_sessions": sessions,
                    "haystack_session_ids": session_ids,
                    "haystack_dates": dates,
                    "question": str(q),
                    "answer_session_ids": list(gold),
                    "question_id": qid,
                }
            )
    return entries


def run_locomo(
    vault: Path,
    cfg: dict[str, Any],
    *,
    limit: int = 0,
    data_path: Path | None = None,
) -> dict[str, Any]:
    from benchmarks.lme_bench import complete_lme_derived_suite, run_lme

    cache = Path(
        os.path.expanduser(
            (cfg.get("benchmark") or {}).get("data_cache_dir", "~/.cache/llm-wiki-benchmarks")
        )
    )
    path = data_path if data_path and data_path.is_file() else download_locomo(cache)
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        return {
            "summary": {
                "suite": "locomo",
                "status": "error",
                "message": "Expected JSON array",
            },
        }

    entries = locomo_to_lme_entries(raw)
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
        top_k=10,
    )
    return complete_lme_derived_suite(
        vault,
        cfg,
        result,
        suite="locomo",
        backend=backend,
        compressor=comp,
        entry_count=len(entries),
    )
