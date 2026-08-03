"""Shared raw/ markdown validation (CLI + MCP)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from lib.raw_markdown import autofix_raw_markdown, raw_file_path, validate_raw_markdown


class RawValidationResult(TypedDict):
    """Stable validation result shared by CLI presentation and MCP JSON output."""

    ok: bool
    valid: bool
    error: str | None
    rel: str
    path: str
    path_obj: Path | None
    issues: list[str]
    autofix_applied: list[str]
    skipped: str | None


def normalize_raw_relpath(path_arg: str) -> str:
    s = path_arg.replace("\\", "/").strip().lstrip("/")
    s = s.removeprefix("raw/")
    return s


def raw_memory_rel_prefix(cfg: dict[str, Any]) -> str:
    mem_dir = (cfg.get("memory") or {}).get("dir", "raw/memory")
    mem_rel = str(Path(mem_dir).as_posix().replace("\\", "/")).strip("/")
    mem_rel = mem_rel.removeprefix("raw/")
    return mem_rel


def validate_raw_file_result(
    vault: Path,
    cfg: dict[str, Any],
    path_arg: str,
    *,
    autofix: bool = False,
) -> RawValidationResult:
    """
    Validate one file under raw/. Optionally apply deterministic autofix first.
    Returns a dict suitable for MCP JSON; CLI prints based on the same fields.
    """
    rel = normalize_raw_relpath(path_arg)
    try:
        path = raw_file_path(vault, rel)
    except SystemExit as e:
        msg = " ".join(str(a) for a in (e.args or ())) or "invalid path"
        return {
            "ok": False,
            "valid": False,
            "error": msg,
            "rel": rel,
            "path": f"raw/{rel}",
            "path_obj": None,
            "issues": [],
            "autofix_applied": [],
            "skipped": None,
        }

    if not path.is_file():
        return {
            "ok": False,
            "valid": False,
            "error": f"Not a file: raw/{rel}",
            "rel": rel,
            "path": f"raw/{rel}",
            "path_obj": path,
            "issues": [],
            "autofix_applied": [],
            "skipped": None,
        }

    mem_rel = raw_memory_rel_prefix(cfg)
    if rel == mem_rel or rel.startswith(mem_rel + "/"):
        return {
            "ok": True,
            "valid": True,
            "error": None,
            "skipped": "session memory",
            "rel": rel,
            "path": f"raw/{rel}",
            "path_obj": path,
            "issues": [],
            "autofix_applied": [],
        }

    text = path.read_text(encoding="utf-8", errors="replace")
    applied: list[str] = []
    if autofix:
        fixed, applied = autofix_raw_markdown(text)
        if applied:
            path.write_text(fixed, encoding="utf-8")
        text = path.read_text(encoding="utf-8", errors="replace")
    issues = validate_raw_markdown(text)
    ok = len(issues) == 0
    return {
        "ok": ok,
        "valid": ok,
        "error": None,
        "rel": rel,
        "path": f"raw/{rel}",
        "path_obj": path,
        "issues": issues,
        "autofix_applied": applied,
        "skipped": None,
    }
