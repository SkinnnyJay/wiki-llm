"""Optional operational metrics — append-only JSONL flat file."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.config_loader import resolve_storage_path

DEFAULT_MAX_FILE_SIZE_MB = 50
BYTES_PER_MEBIBYTE = 1_048_576


def _mapping_or_empty(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _max_file_size_bytes(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return DEFAULT_MAX_FILE_SIZE_MB * BYTES_PER_MEBIBYTE
    try:
        size_mb = float(value)
    except ValueError:
        return DEFAULT_MAX_FILE_SIZE_MB * BYTES_PER_MEBIBYTE
    if size_mb < 0:
        return DEFAULT_MAX_FILE_SIZE_MB * BYTES_PER_MEBIBYTE
    return int(size_mb * BYTES_PER_MEBIBYTE)


def _atomic_write_text(path: Path, text: str) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(text, encoding="utf-8")
    os.replace(temporary_path, path)


def _parse_metric_record(line: str) -> dict[str, object] | None:
    try:
        value: object = json.loads(line)  # pyright: ignore[reportAny] -- validated below
    except json.JSONDecodeError:
        return None
    return _mapping_or_empty(value) or None


class MetricsRecorder:
    """Append-only JSONL metrics writer.  All methods are no-ops when disabled."""

    def __init__(self, vault: Path, cfg: dict[str, Any]):
        metrics_config = _mapping_or_empty(cfg.get("metrics"))
        self._enabled = metrics_config.get("enabled") is True
        self._max_bytes = _max_file_size_bytes(
            metrics_config.get("max_file_size_mb", DEFAULT_MAX_FILE_SIZE_MB)
        )
        if self._enabled:
            self._path = resolve_storage_path(vault, cfg, "metrics_db")
            self._path.parent.mkdir(parents=True, exist_ok=True)
        else:
            self._path = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def record(
        self,
        key: str,
        value: float | str,
        *,
        meta: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        if not self._enabled or self._path is None:
            return
        try:
            if self._path.exists() and self._path.stat().st_size >= self._max_bytes:
                return
        except OSError:
            pass
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "key": key,
            "value": value,
        }
        if meta:
            entry["meta"] = meta
        if tags:
            entry["tags"] = tags
        line = json.dumps(entry, separators=(",", ":"), default=str) + "\n"
        try:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass

    def query(
        self,
        *,
        key: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not self._enabled or self._path is None or not self._path.exists():
            return []
        results: list[dict[str, Any]] = []
        try:
            with self._path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = _parse_metric_record(line)
                    if rec is None:
                        continue
                    if key and rec.get("key") != key:
                        continue
                    if since and str(rec.get("ts", "")) < since:
                        continue
                    results.append(rec)
        except OSError:
            pass
        return results[-limit:]

    def stats(self) -> dict[str, Any]:
        if not self._enabled or self._path is None:
            return {"enabled": False}
        if not self._path.exists():
            return {"enabled": True, "path": str(self._path), "records": 0, "size_bytes": 0}
        size = 0
        count = 0
        keys: dict[str, int] = {}
        first_ts = ""
        last_ts = ""
        try:
            size = self._path.stat().st_size
            with self._path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = _parse_metric_record(line)
                    if rec is None:
                        continue
                    count += 1
                    k = str(rec.get("key", "?"))
                    keys[k] = keys.get(k, 0) + 1
                    ts = str(rec.get("ts", ""))
                    if not first_ts:
                        first_ts = ts
                    last_ts = ts
        except OSError:
            pass
        return {
            "enabled": True,
            "path": str(self._path),
            "records": count,
            "size_bytes": size,
            "keys": keys,
            "first_ts": first_ts,
            "last_ts": last_ts,
        }

    def clear(self, *, before: str | None = None) -> dict[str, Any]:
        """Truncate or prune entries older than *before* (ISO-8601 date prefix)."""
        if not self._enabled or self._path is None or not self._path.exists():
            return {"removed": 0}
        if before is None:
            removed = 0
            try:
                with self._path.open(encoding="utf-8") as f:
                    removed = sum(1 for ln in f if ln.strip())
            except OSError:
                pass
            _atomic_write_text(self._path, "")
            return {"removed": removed}
        kept: list[str] = []
        removed = 0
        try:
            with self._path.open(encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    rec = _parse_metric_record(stripped)
                    if rec is None:
                        kept.append(line)
                        continue
                    if str(rec.get("ts", "")) < before:
                        removed += 1
                    else:
                        kept.append(line)
        except OSError:
            return {"removed": 0}
        _atomic_write_text(self._path, "".join(kept))
        return {"removed": removed}


class _NoopMetrics:
    """Drop-in replacement that silently discards all writes."""

    enabled = False

    def record(
        self,
        key: str,
        value: float | str,
        *,
        meta: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        pass

    def query(
        self, *, key: str | None = None, since: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        return []

    def stats(self) -> dict[str, Any]:
        return {"enabled": False}

    def clear(self, *, before: str | None = None) -> dict[str, Any]:
        return {"removed": 0}


NOOP = _NoopMetrics()


def get_metrics(vault: Path, cfg: dict[str, Any]) -> MetricsRecorder | _NoopMetrics:
    if _mapping_or_empty(cfg.get("metrics")).get("enabled") is True:
        return MetricsRecorder(vault, cfg)
    return NOOP
