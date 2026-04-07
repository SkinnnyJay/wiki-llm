"""Resolve vault directory (contains config.json, raw/, wiki/)."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_vault(cwd: Path | None = None, override: str | None = None) -> Path:
    if override:
        return Path(override).resolve()
    env = os.environ.get("LLM_WIKI_VAULT")
    if env:
        return Path(env).resolve()
    base = (cwd or Path.cwd()).resolve()
    candidate = base / "llm-wiki"
    if (candidate / "config.json").is_file():
        return candidate
    # Allow running from inside vault
    if (base / "config.json").is_file() and (base / "wiki").is_dir():
        return base
    return candidate  # default expected path even if not created yet


def plugin_root() -> Path:
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if root:
        return Path(root).resolve()
    # scripts/lib/paths.py -> plugin root is parents[2]
    return Path(__file__).resolve().parents[2]


def raw_destination(vault: Path, relative: Path | str) -> Path:
    """
    Resolve vault/raw/<relative>, ensuring the result stays under raw/.
    Rejects absolute paths and .. sequences that escape raw/.
    """
    rel = Path(relative)
    if rel.is_absolute():
        raise SystemExit("--out must be a relative path under llm-wiki/raw/ (absolute paths are not allowed)")
    raw_root = (vault / "raw").resolve()
    raw_root.mkdir(parents=True, exist_ok=True)
    dest = (raw_root / rel).resolve()
    try:
        dest.relative_to(raw_root)
    except ValueError:
        raise SystemExit(f"Output path escapes raw/: {rel.as_posix()}") from None
    return dest
