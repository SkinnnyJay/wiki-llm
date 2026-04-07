"""Deterministic validation and safe autofix for markdown under vault raw/."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def raw_file_path(vault: Path, relative: str | Path) -> Path:
    """Resolve vault/raw/<relative>; reject escapes."""
    rel = Path(relative)
    if rel.is_absolute():
        raise SystemExit("Path must be relative to raw/, not absolute")
    raw_root = (vault / "raw").resolve()
    dest = (raw_root / rel).resolve()
    try:
        dest.relative_to(raw_root)
    except ValueError:
        raise SystemExit(f"Path escapes raw/: {rel.as_posix()}") from None
    return dest


def validate_raw_markdown(text: str) -> list[str]:
    """Return human-readable issues (empty list = OK for structural checks)."""
    issues: list[str] = []
    if "\x00" in text:
        issues.append("contains NUL byte")

    lines = text.split("\n")
    fence_lines = [i for i, line in enumerate(lines, 1) if line.strip().startswith("```")]
    if len(fence_lines) % 2 != 0:
        issues.append(
            f"unbalanced fenced code blocks ({len(fence_lines)} ``` lines — expected even count)"
        )

    max_line = 200_000
    for i, line in enumerate(lines, 1):
        if len(line) > max_line:
            issues.append(f"line {i} exceeds {max_line} characters")

    # Odd lone carriage returns (mixed line endings) — warning-style
    if "\r\n" in text and "\r" in text.replace("\r\n", ""):
        issues.append("mixed line endings (CRLF with stray CR)")

    return issues


def autofix_raw_markdown(text: str) -> tuple[str, list[str]]:
    """Apply safe deterministic fixes; return (new_text, descriptions)."""
    applied: list[str] = []
    # Normalize line endings to \n
    if "\r\n" in text:
        text = text.replace("\r\n", "\n")
        applied.append("normalized CRLF to LF")
    elif "\r" in text:
        text = text.replace("\r", "\n")
        applied.append("normalized CR to LF")

    lines = text.split("\n")
    stripped = [line.rstrip() for line in lines]
    if stripped != lines:
        applied.append("stripped trailing whitespace per line")
    out = "\n".join(stripped)
    if not out.endswith("\n"):
        out += "\n"
        applied.append("added final newline")
    return out, applied


def append_preparation_log(
    vault: Path,
    *,
    rel_path: str,
    goal: str,
    action: str,
    notes: str = "",
) -> Path:
    """Append one JSON line to raw/.preparation-log.jsonl."""
    raw_dir = vault / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    log_path = raw_dir / ".preparation-log.jsonl"
    entry: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "path": rel_path.replace("\\", "/"),
        "goal": goal,
        "action": action,
    }
    if notes.strip():
        entry["notes"] = notes.strip()
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)
    return log_path
