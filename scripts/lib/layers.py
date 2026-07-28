"""Layered context protocol: wake-up blob and CLAUDE.md Memory Stack update."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lib.json_index import CorruptIndexError, load_json_object


def _load_tags_index(vault: Path) -> dict[str, list[str]]:
    p = vault / "raw" / ".tags.json"
    try:
        data = load_json_object(p, default_if_missing={})
    except CorruptIndexError:
        raise
    if not isinstance(data, dict):
        raise CorruptIndexError(p, "tags index root must be a JSON object")
    out: dict[str, list[str]] = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, list):
            out[k] = [str(x) for x in v]
    return out


def _load_recent_log(vault: Path, n: int = 3) -> list[str]:
    log = vault / "wiki" / "log.md"
    if not log.exists():
        return []
    lines = [l.strip() for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    # Find lines that look like log entries (start with - or *)
    entries = [l.lstrip("-* ").strip() for l in lines if l.startswith(("-", "*"))]
    return entries[-n:]


def wiki_page_for_tag(vault: Path, tag: str) -> str | None:
    """Return relative path to wiki page for tag, or None."""
    candidates = [
        vault / "wiki" / f"{tag}.md",
        vault / "wiki" / "topics" / f"{tag}.md",
    ]
    for c in candidates:
        if c.exists():
            return str(c.relative_to(vault))
    return None


# Back-compat private alias
_wiki_page_for_tag = wiki_page_for_tag

def _approx_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token) for budgeting."""
    return max(1, len(text) // 4)


def build_wake_up(vault: Path, cfg: dict[str, Any]) -> str:
    """Generate L0+L1 context blob (default target ~170–200 tokens)."""
    persona = (cfg.get("persona") or {}).get("name") or "Gennie"
    version = cfg.get("version") or "?"
    layers_cfg = (cfg.get("layers") or {}) if isinstance(cfg, dict) else {}
    max_tokens = int(layers_cfg.get("wake_max_tokens", 200))
    l1_bullets = int(layers_cfg.get("l1_topic_bullets", 8))

    tags_index = _load_tags_index(vault)
    recent = _load_recent_log(vault)

    raw_count = len(list((vault / "raw").rglob("*.md"))) if (vault / "raw").exists() else 0
    wiki_count = len(list((vault / "wiki").rglob("*.md"))) if (vault / "wiki").exists() else 0

    # Build topic list sorted by file count desc, top N
    topics_sorted = sorted(tags_index.items(), key=lambda kv: -len(kv[1]))[: max(1, l1_bullets)]
    overflow = max(0, len(tags_index) - l1_bullets)

    topic_parts = []
    for tag, files in topics_sorted:
        wiki_page = _wiki_page_for_tag(vault, tag)
        if wiki_page:
            topic_parts.append(f"{tag} ({len(files)} raw → {wiki_page} ✓)")
        else:
            topic_parts.append(f"{tag} ({len(files)} raw ⚠ no wiki page)")

    if not topic_parts:
        topics_line = "L1 topics: (none yet — run llm-wiki ingest with --tags)"
    else:
        suffix = f" (+ {overflow} more)" if overflow else ""
        topics_line = "L1 topics: " + " · ".join(topic_parts) + suffix

    lines = [
        f"L0 identity: assistant for **{persona}** (llm-wiki v{version})",
        topics_line,
        f"Corpus: {wiki_count} wiki pages | {raw_count} raw files",
    ]
    if recent:
        lines.append("Recent log: " + " · ".join(recent))

    blob = "\n".join(lines) + "\n"
    # Soft trim if over budget (keep head lines)
    while _approx_tokens(blob) > max_tokens and len(lines) > 2:
        lines.pop()
        blob = "\n".join(lines) + "\n"
    return blob


def update_claude_md(vault: Path, cfg: dict[str, Any]) -> None:
    """Refresh ## Memory Stack section in llm-wiki/CLAUDE.md."""
    claude_md = vault / "CLAUDE.md"
    if not claude_md.exists():
        return  # non-standard layout, skip silently

    blob = build_wake_up(vault, cfg)
    section = (
        "## Memory Stack\n\n"
        "<!-- Auto-updated by: llm-wiki wake-up --update-claude -->\n"
        f"{blob}\n"
        "**L2 (on-demand)** Open wiki/ pages for the active tag/topic; use `wing`/`room` in frontmatter to narrow scope.\n"
        "**L3 (on-demand)** Full vault search (`llm-wiki` search / MCP `wiki_search`) when L2 is insufficient.\n"
    )

    text = claude_md.read_text(encoding="utf-8")
    # Replace existing section
    pattern = re.compile(r"## Memory Stack\n.*?(?=\n## |\Z)", re.DOTALL)
    if pattern.search(text):
        new_text = pattern.sub(section.rstrip("\n"), text)
    else:
        new_text = text.rstrip("\n") + "\n\n" + section
    claude_md.write_text(new_text, encoding="utf-8")
