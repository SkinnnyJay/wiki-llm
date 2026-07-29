"""Wiki page frontmatter schema for compiled knowledge pages."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

# Reserved / structural wiki files that may omit full provenance schema.
SCHEMA_EXEMPT_NAMES = frozenset(
    {
        "index.md",
        "log.md",
        "overview.md",
        "hints.md",
        "hot.md",
        "MEMORY.md",
        "SOUL.md",
        "CRITICAL_FACTS.md",
        "CLAUDE.md",
    }
)

OPTIONAL_SCHEMA_KEYS = (
    "confidence",
    "sources",
    "last_verified",
    "contradictions",
    "review_required",
    "stale_after",
    "generated_by",
    "title",
    "updated",
    "tags",
)


def parse_wiki_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Best-effort YAML-ish frontmatter parse (stdlib only; subset)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    block = text[3:end].strip("\n")
    body = text[end + 4 :].lstrip("\n")
    fm: dict[str, Any] = {}
    key: str | None = None
    list_acc: list[str] | None = None
    for line in block.splitlines():
        if list_acc is not None and line.strip().startswith("- "):
            list_acc.append(line.strip()[2:].strip().strip("\"'"))
            continue
        if list_acc is not None and key is not None:
            fm[key] = list_acc
            list_acc = None
            key = None
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        if v == "" or v == "|" or v == ">":
            key = k
            list_acc = []
            continue
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            fm[k] = (
                [p.strip().strip("\"'") for p in inner.split(",") if p.strip()]
                if inner
                else []
            )
            continue
        if v.lower() in ("true", "false"):
            fm[k] = v.lower() == "true"
            continue
        try:
            if "." in v:
                fm[k] = float(v)
            else:
                fm[k] = int(v)
            continue
        except ValueError:
            pass
        fm[k] = v.strip("\"'")
    if list_acc is not None and key is not None:
        fm[key] = list_acc
    return fm, body


def _as_str_list(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    if isinstance(val, str) and val.strip():
        return [val.strip()]
    return []


def validate_page_schema(
    path: Path,
    text: str,
    *,
    require_sources: bool = False,
    require_updated: bool = False,
) -> list[str]:
    """Return human-readable issues for one wiki page (empty = ok)."""
    name = path.name
    if name in SCHEMA_EXEMPT_NAMES:
        return []
    rel = path.as_posix()
    if "/.og/" in rel or rel.endswith("/.og"):
        return []
    fm, _ = parse_wiki_frontmatter(text)
    issues: list[str] = []
    if require_sources:
        sources = _as_str_list(fm.get("sources") or fm.get("llm_wiki_sources"))
        if not sources:
            issues.append("missing sources: (or llm_wiki_sources)")
    if require_updated and not (fm.get("updated") or fm.get("last_verified")):
        issues.append("missing updated: or last_verified:")
    conf = fm.get("confidence")
    if conf is not None:
        try:
            c = float(conf)
            if c < 0.0 or c > 1.0:
                issues.append(f"confidence out of range [0,1]: {conf}")
        except (TypeError, ValueError):
            issues.append(f"confidence not a number: {conf}")
    if "review_required" in fm and not isinstance(fm["review_required"], bool):
        if str(fm["review_required"]).lower() not in ("true", "false", "1", "0"):
            issues.append("review_required must be boolean")
    return issues


def is_stale(
    fm: dict[str, Any],
    *,
    mtime: float | None = None,
    now: date | None = None,
) -> bool:
    """True if stale_after days since updated/last_verified (or mtime fallback)."""
    now_d = now or date.today()
    raw = fm.get("stale_after")
    if raw is None:
        return False
    try:
        days = int(raw) if not isinstance(raw, int) else raw
    except (TypeError, ValueError):
        return False
    if days <= 0:
        return False
    anchor = fm.get("last_verified") or fm.get("updated")
    anchor_d: date | None = None
    if isinstance(anchor, str) and len(anchor) >= 10:
        try:
            anchor_d = date.fromisoformat(anchor[:10])
        except ValueError:
            anchor_d = None
    if anchor_d is None and mtime is not None:
        anchor_d = datetime.fromtimestamp(mtime).date()
    if anchor_d is None:
        return False
    return (now_d - anchor_d).days > days
