"""Load repo-local .env files into os.environ (stdlib only; no python-dotenv)."""

from __future__ import annotations

import os
from pathlib import Path


def _parse_env_line(line: str) -> tuple[str, str] | None:
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if s.startswith("export "):
        s = s[7:].strip()
    if "=" not in s:
        return None
    key, _, rest = s.partition("=")
    key = key.strip()
    if not key:
        return None
    val = rest.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
        val = val[1:-1]
    return key, val


def load_plugin_dotenv(
    plugin_root: Path,
    *,
    override: bool = False,
) -> None:
    """
    Merge ``.env`` then ``.env.local`` from ``plugin_root`` (later file wins per key).
    Then apply to ``os.environ``: existing process environment wins unless
    ``override`` is True (same idea as python-dotenv).
    """
    merged: dict[str, str] = {}
    for name in (".env", ".env.local"):
        path = plugin_root / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            parsed = _parse_env_line(line)
            if not parsed:
                continue
            k, v = parsed
            merged[k] = v
    for k, v in merged.items():
        if not override and k in os.environ:
            continue
        os.environ[k] = v
