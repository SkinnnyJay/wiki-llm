"""Shared helpers for on-disk JSON indexes that must fail closed when corrupt."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

_log = logging.getLogger("llm_wiki.json_index")


class CorruptIndexError(Exception):
    """Raised when an on-disk JSON index is unreadable or invalid."""

    def __init__(self, path: Path, message: str) -> None:
        self.path = path
        super().__init__(f"{path}: {message}")


def quarantine_corrupt(path: Path, exc: BaseException | None = None) -> Path:
    """
    Rename a corrupt index aside so a later write cannot silently wipe it.

    Returns the quarantine path.
    """
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    dest = path.with_name(f"{path.name}.corrupt.{ts}")
    n = 0
    while dest.exists():
        n += 1
        dest = path.with_name(f"{path.name}.corrupt.{ts}.{n}")
    try:
        os.replace(path, dest)
        _log.error(
            "Quarantined corrupt index %s -> %s (%s)",
            path,
            dest,
            exc or "invalid",
        )
    except OSError as e:
        _log.error("Failed to quarantine corrupt index %s: %s", path, e)
        raise CorruptIndexError(path, f"corrupt and could not quarantine: {e}") from e
    return dest


def load_json_object(
    path: Path,
    *,
    default_if_missing: dict[str, Any] | None = None,
    require_mapping: bool = True,
) -> dict[str, Any]:
    """
    Load a JSON object from disk.

    Missing file → ``default_if_missing`` (or {}).
    Corrupt / non-object → quarantine and raise CorruptIndexError (fail closed).
    """
    if default_if_missing is None:
        default_if_missing = {}
    if not path.exists():
        return dict(default_if_missing)
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception as e:
        quarantine_corrupt(path, e)
        raise CorruptIndexError(path, f"invalid JSON ({e})") from e
    if require_mapping and not isinstance(data, dict):
        quarantine_corrupt(path, ValueError("not a JSON object"))
        raise CorruptIndexError(path, "JSON root must be an object")
    return data  # type: ignore[return-value]


def atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON atomically via a sibling .tmp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)
