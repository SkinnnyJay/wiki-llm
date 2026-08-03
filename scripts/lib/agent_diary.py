"""Per-agent append-only diary under raw/agents/<id>/diary.md."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def _diary_path(vault: Path, agent_id: str) -> Path:
    safe = "".join(c for c in agent_id if c.isalnum() or c in "-_")[:64] or "default"
    return vault / "raw" / "agents" / safe / "diary.md"


def read_diary(vault: Path, agent_id: str, *, max_chars: int = 0) -> str:
    p = _diary_path(vault, agent_id)
    if not p.is_file():
        return ""
    text = p.read_text(encoding="utf-8", errors="replace")
    if max_chars and len(text) > max_chars:
        return text[:max_chars] + "\n…"
    return text


def append_diary(vault: Path, agent_id: str, line: str, *, source: str | None = None) -> Path:
    p = _diary_path(vault, agent_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prefix = f"- [{ts}]"
    if source:
        prefix += f" ({source})"
    block = f"{prefix} {line.strip()}\n"
    if p.exists():
        p.write_text(p.read_text(encoding="utf-8", errors="replace") + block, encoding="utf-8")
    else:
        p.write_text(
            "---\n"
            "title: Agent diary\n"
            f"llm_wiki_tags: [agent-diary, {agent_id}]\n"
            "---\n\n"
            "# Diary\n\n" + block,
            encoding="utf-8",
        )
    return p
