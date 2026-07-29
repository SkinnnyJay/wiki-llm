"""CLI output helpers — JSON and human-friendly streams."""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO


def emit_json(data: Any, *, stream: TextIO | None = None) -> None:
    """Write ``data`` as UTF-8 JSON (pretty) to stdout (or ``stream``)."""
    out = stream or sys.stdout
    out.write(json.dumps(data, indent=2, default=str))
    out.write("\n")


def emit_line(msg: str = "", *, stream: TextIO | None = None) -> None:
    """Write one human-readable line."""
    out = stream or sys.stdout
    out.write(msg)
    if not msg.endswith("\n"):
        out.write("\n")


def is_tty(stream: TextIO | None = None) -> bool:
    """True when the stream is an interactive terminal."""
    s = stream or sys.stdout
    try:
        return bool(s.isatty())
    except Exception:
        return False


def ok_mark(*, stream: TextIO | None = None) -> str:
    """Status mark for success — Unicode on TTY, ASCII otherwise."""
    return "✓" if is_tty(stream) else "OK"


def fail_mark(*, stream: TextIO | None = None) -> str:
    """Status mark for failure — Unicode on TTY, ASCII otherwise."""
    return "✗" if is_tty(stream) else "FAIL"
