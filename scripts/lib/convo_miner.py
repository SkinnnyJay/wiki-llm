"""Normalize chat exports into exchange-pair markdown chunks."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def exchange_pairs_from_lines(
    lines: list[str],
    *,
    user_markers: tuple[str, ...] = ("User:", "Human:", "You:"),
    assistant_markers: tuple[str, ...] = ("Assistant:", "AI:", "Claude:", "GPT:"),
) -> list[tuple[str, str]]:
    """Pair consecutive user/assistant blocks (best-effort for plain transcripts)."""
    pairs: list[tuple[str, str]] = []
    pending_user: str | None = None
    for line in lines:
        s = line.strip()
        if not s:
            continue
        low = s[:12].lower()
        is_user = any(s.startswith(m) for m in user_markers)
        is_asst = any(s.startswith(m) for m in assistant_markers)
        if is_user:
            pending_user = s
        elif is_asst and pending_user:
            pairs.append((pending_user, s))
            pending_user = None
    return pairs


def normalize_transcript_to_markdown(text: str, *, title: str = "Conversation") -> str:
    """
    Convert loose transcript or JSONL-ish content into markdown with ## Exchange sections.
    """
    lines = text.splitlines()
    pairs = exchange_pairs_from_lines(lines)
    if not pairs:
        # Fallback: chunk non-empty lines as single-column notes
        chunks = [ln.strip() for ln in lines if ln.strip()]
        body = "\n\n".join(f"- {c}" for c in chunks[:200])
        return f"---\ntitle: {title}\n---\n\n# Transcript\n\n{body}\n"

    parts: list[str] = [f"---\ntitle: {title}\n---\n\n# Conversation\n"]
    for i, (u, a) in enumerate(pairs, 1):
        parts.append(f"\n## Exchange {i}\n\n**User:** {u}\n\n**Assistant:** {a}\n")
    return "".join(parts)


def parse_claude_code_jsonl(path: Path) -> str:
    """Best-effort: read JSON lines with role/content fields."""
    turns: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = str(obj.get("role") or obj.get("type") or "").lower()
        content = str(obj.get("content") or obj.get("text") or "").strip()
        if not content:
            continue
        if role in ("user", "human"):
            turns.append(("user", content))
        elif role in ("assistant", "ai", "model"):
            turns.append(("assistant", content))
    pairs: list[tuple[str, str]] = []
    i = 0
    while i + 1 < len(turns):
        if turns[i][0] == "user" and turns[i + 1][0] == "assistant":
            pairs.append((turns[i][1], turns[i + 1][1]))
            i += 2
        else:
            i += 1
    if not pairs:
        return normalize_transcript_to_markdown(path.read_text(encoding="utf-8", errors="replace"))
    parts = [f"---\ntitle: {path.stem}\n---\n\n# Conversation (JSONL)\n"]
    for j, (u, a) in enumerate(pairs, 1):
        parts.append(f"\n## Exchange {j}\n\n**User:** {u}\n\n**Assistant:** {a}\n")
    return "".join(parts)


def process_convo_file(src: Path) -> str:
    """Dispatch on filename / sniff JSON vs plain text."""
    text = src.read_text(encoding="utf-8", errors="replace")
    if src.suffix.lower() == ".jsonl" or text.strip().startswith("{"):
        try:
            return parse_claude_code_jsonl(src)
        except Exception:
            pass
    return normalize_transcript_to_markdown(text, title=src.stem)
