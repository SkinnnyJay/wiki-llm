"""Layered context protocol: wake-up blob and CLAUDE.md Memory Stack update."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _load_tags_index(vault: Path) -> dict[str, list[str]]:
    p = vault / "raw" / ".tags.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_recent_log(vault: Path, n: int = 3) -> list[str]:
    log = vault / "wiki" / "log.md"
    if not log.exists():
        return []
    lines = [l.strip() for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    # Find lines that look like log entries (start with - or *)
    entries = [l.lstrip("-* ").strip() for l in lines if l.startswith(("-", "*"))]
    return entries[-n:]


def _wiki_page_for_tag(vault: Path, tag: str) -> str | None:
    """Return relative path to wiki page for tag, or None."""
    candidates = [
        vault / "wiki" / f"{tag}.md",
        vault / "wiki" / "topics" / f"{tag}.md",
    ]
    for c in candidates:
        if c.exists():
            return str(c.relative_to(vault))
    return None


def build_wake_up(vault: Path, cfg: dict[str, Any]) -> str:
    """Generate L0+L1 context blob (target ≤200 tokens)."""
    persona = (cfg.get("persona") or {}).get("name") or "Gennie"
    version = cfg.get("version") or "?"

    tags_index = _load_tags_index(vault)
    recent = _load_recent_log(vault)

    raw_count = len(list((vault / "raw").rglob("*.md"))) if (vault / "raw").exists() else 0
    wiki_count = len(list((vault / "wiki").rglob("*.md"))) if (vault / "wiki").exists() else 0

    # Build topic list sorted by file count desc, top 10
    topics_sorted = sorted(tags_index.items(), key=lambda kv: -len(kv[1]))[:10]
    overflow = max(0, len(tags_index) - 10)

    topic_parts = []
    for tag, files in topics_sorted:
        wiki_page = _wiki_page_for_tag(vault, tag)
        if wiki_page:
            topic_parts.append(f"{tag} ({len(files)} raw → {wiki_page} ✓)")
        else:
            topic_parts.append(f"{tag} ({len(files)} raw ⚠ no wiki page)")

    if not topic_parts:
        topics_line = "Topics: (none yet — run llm-wiki ingest with --tags)"
    else:
        suffix = f" (+ {overflow} more)" if overflow else ""
        topics_line = "Topics: " + " · ".join(topic_parts) + suffix

    lines = [
        f"## Vault: {persona}  (llm-wiki v{version})",
        topics_line,
        f"Wiki pages: {wiki_count} | raw/ files: {raw_count}",
    ]
    if recent:
        lines.append("Recent: " + " · ".join(recent))

    return "\n".join(lines) + "\n"


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
        "**L2** Open wiki/ pages tagged for the current topic.\n"
        "**L3** Search raw/ and outputs/ when wiki/ answer is insufficient.\n"
    )

    text = claude_md.read_text(encoding="utf-8")
    # Replace existing section
    pattern = re.compile(r"## Memory Stack\n.*?(?=\n## |\Z)", re.DOTALL)
    if pattern.search(text):
        new_text = pattern.sub(section.rstrip("\n"), text)
    else:
        new_text = text.rstrip("\n") + "\n\n" + section
    claude_md.write_text(new_text, encoding="utf-8")
