"""Tag detection and tag index management for raw/ ingest."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TagResult:
    tags: list[str]
    source: str  # "auto" | "manual" | "llm" | sorted combinations joined with "+"


def _normalise(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for t in tags:
        t = t.strip().lower().replace(" ", "-")
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return sorted(out)


def detect_tags(text: str, path: Path, cfg: dict[str, Any]) -> TagResult:
    """Heuristic-only tag detection. Never calls LLM."""
    tags: list[str] = []

    # 1. Path segments (exclude generic names)
    _SKIP = {"raw", "wiki", "outputs", "notes", "misc", "general", "inbox"}
    for part in path.parts:
        p = re.sub(r"\..*$", "", part).lower()
        if p and p not in _SKIP and not p.startswith("."):
            tags.append(p)

    # 2. First H1 or H2 heading — split on spaces and common separators
    heading = re.search(r"^#{1,2}\s+(.+)", text, re.MULTILINE)
    if heading:
        words = re.findall(r"[a-z]+", heading.group(1).lower())
        _STOP = {"the", "a", "an", "and", "or", "of", "in", "on", "for", "to", "with", "how", "why"}
        tags.extend(w for w in words if len(w) > 3 and w not in _STOP)

    # 3. Obsidian-style tags: frontmatter
    fm_match = re.search(r"^tags:\s*\[([^\]]+)\]", text, re.MULTILINE)
    if fm_match:
        tags.extend(t.strip().strip("'\"") for t in fm_match.group(1).split(","))
    fm_block = re.search(r"^tags:\s*\n((?:\s*-\s*.+\n)+)", text, re.MULTILINE)
    if fm_block:
        tags.extend(re.findall(r"-\s*(.+)", fm_block.group(1)))

    return TagResult(tags=_normalise(tags), source="auto")


def detect_tags_llm(text: str, cfg: dict[str, Any]) -> list[str]:
    """Call configured LLM for tag suggestions. Returns raw list."""
    # Stub — full implementation requires LLM adapter integration.
    # When ingestion_tagging.llm_detect is true, caller invokes this.
    return []


def merge_tags(
    auto: list[str],
    manual: list[str],
    llm: list[str],
) -> TagResult:
    """Merge tag lists and determine source string."""
    combined = _normalise(auto + manual + llm)
    sources = []
    if auto:
        sources.append("auto")
    if llm:
        sources.append("llm")
    if manual:
        sources.append("manual")
    source = "+".join(sorted(sources)) if sources else "auto"
    return TagResult(tags=combined, source=source)


# ── Tag index (.tags.json) ──────────────────────────────────────────────────

def _index_path(vault: Path) -> Path:
    return vault / "raw" / ".tags.json"


def _load_index(vault: Path) -> dict[str, list[str]]:
    p = _index_path(vault)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_index(vault: Path, index: dict[str, list[str]]) -> None:
    p = _index_path(vault)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def register_tags(vault: Path, tags: list[str], path: Path) -> None:
    """Add path under each tag in .tags.json. Atomic write."""
    index = _load_index(vault)
    str_path = str(path)
    for tag in tags:
        existing = index.get(tag, [])
        if str_path not in existing:
            index[tag] = existing + [str_path]
    _save_index(vault, index)


def rebuild_tag_index(vault: Path) -> int:
    """Rebuild .tags.json from llm_wiki_tags frontmatter. Returns file count."""
    raw_dir = vault / "raw"
    if not raw_dir.exists():
        return 0
    index: dict[str, list[str]] = {}
    count = 0
    for md in sorted(raw_dir.rglob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^llm_wiki_tags:\s*\[([^\]]+)\]", text, re.MULTILINE)
        if m:
            tags = [t.strip() for t in m.group(1).split(",")]
            sp = str(md)
            for tag in tags:
                index.setdefault(tag, [])
                if sp not in index[tag]:
                    index[tag].append(sp)
            count += 1
    _save_index(vault, index)
    return count
