"""Claim IR: extract citation-backed claims from compiled wiki pages."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from lib.wiki_schema import SCHEMA_EXEMPT_NAMES, parse_wiki_frontmatter

_SOURCE_INLINE = re.compile(
    r"(?:source|cite[sd]?)\s*:\s*`?(raw/[^\s`|]+)`?",
    re.IGNORECASE,
)
_BACKTICK_RAW = re.compile(r"`(raw/[^`]+)`")
_CLAIM_LINE = re.compile(r"^[-*]\s+(.+)$")


def _claim_id(page: str, text: str) -> str:
    raw = f"{page}|{text.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def normalize_raw_rel(raw_rel: str) -> str:
    """Normalize to vault-relative ``raw/...`` form."""
    s = (raw_rel or "").strip().replace("\\", "/").lstrip("./")
    if s.startswith("llm-wiki/"):
        s = s[len("llm-wiki/") :]
    if not s.startswith("raw/"):
        s = f"raw/{s}"
    return s


def page_sources_list(fm: dict[str, Any]) -> list[str]:
    page_sources = fm.get("sources") or fm.get("llm_wiki_sources") or []
    if isinstance(page_sources, str):
        page_sources = [page_sources]
    return [str(s).replace("\\", "/") for s in page_sources]


def pages_citing_raw(vault: Path, raw_rel: str) -> list[str]:
    """Return wiki-relative paths (``topic.md``) that cite ``raw_rel`` in sources or body."""
    needle = normalize_raw_rel(raw_rel)
    wiki = vault / "wiki"
    if not wiki.is_dir():
        return []
    out: list[str] = []
    for path in sorted(wiki.rglob("*.md")):
        if ".og" in path.parts:
            continue
        rel = path.relative_to(wiki).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, body = parse_wiki_frontmatter(text)
        sources = page_sources_list(fm)
        if any(normalize_raw_rel(s) == needle for s in sources):
            out.append(rel)
            continue
        if needle in body.replace("\\", "/"):
            out.append(rel)
    return out


def extract_claims_from_text(page_rel: str, text: str) -> list[dict[str, Any]]:
    """
    Heuristic claim extraction from wiki markdown.

    - Prefer bullet lines that cite ``raw/...`` paths.
    - Attach page frontmatter ``sources`` / ``confidence`` when present.
    """
    fm, body = parse_wiki_frontmatter(text)
    page_sources = page_sources_list(fm)
    conf = fm.get("confidence")
    try:
        conf_f = float(conf) if conf is not None else None
    except (TypeError, ValueError):
        conf_f = None

    claims: list[dict[str, Any]] = []
    for line in body.splitlines():
        m = _CLAIM_LINE.match(line.strip())
        if not m:
            continue
        content = m.group(1).strip()
        inline = [x.strip() for x in _SOURCE_INLINE.findall(content)]
        ticks = [x.strip() for x in _BACKTICK_RAW.findall(content)]
        sources = list(dict.fromkeys([*inline, *ticks]))
        if not sources and not page_sources:
            continue
        if not sources:
            # Bullet without inline cite still counts if page has sources
            sources = list(page_sources)
        claims.append(
            {
                "id": _claim_id(page_rel, content),
                "page": page_rel,
                "text": content,
                "sources": sources,
                "confidence": conf_f,
                "uncited": len(inline) + len(ticks) == 0 and not page_sources,
            }
        )
    return claims


def extract_vault_claims(
    vault: Path, *, only_pages: list[str] | None = None
) -> list[dict[str, Any]]:
    wiki = vault / "wiki"
    if not wiki.is_dir():
        return []
    allow = {p.replace("\\", "/") for p in (only_pages or [])} or None
    out: list[dict[str, Any]] = []
    for path in sorted(wiki.rglob("*.md")):
        if ".og" in path.parts or path.name in SCHEMA_EXEMPT_NAMES:
            continue
        rel = path.relative_to(wiki).as_posix()
        if allow is not None and rel not in allow and path.name not in allow:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        out.extend(extract_claims_from_text(rel, text))
    return out


def write_claims_index(
    vault: Path,
    claims: list[dict[str, Any]] | None = None,
    *,
    only_pages: list[str] | None = None,
) -> Path:
    """
    Write ``outputs/claims.json``.

    When ``only_pages`` is set, merge updated claims for those pages into any
    existing index (surgical recompile).
    """
    if claims is None:
        claims = extract_vault_claims(vault, only_pages=only_pages)

    out_dir = vault / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "claims.json"

    if only_pages:
        allow = {p.replace("\\", "/") for p in only_pages}
        existing: list[dict[str, Any]] = []
        if path.is_file():
            try:
                prev = json.loads(path.read_text(encoding="utf-8"))
                existing = list(prev.get("claims") or [])
            except (OSError, json.JSONDecodeError, TypeError):
                existing = []
        kept = [
            c
            for c in existing
            if str(c.get("page", "")).replace("\\", "/") not in allow
        ]
        claims = kept + list(claims)

    payload = {
        "count": len(claims),
        "uncited": sum(1 for c in claims if c.get("uncited")),
        "claims": claims,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def uncited_claim_issues(claims: list[dict[str, Any]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for c in claims:
        if c.get("uncited"):
            issues.append(
                {
                    "code": "uncited_claim",
                    "path": str(c.get("page")),
                    "message": f"claim lacks sources: {str(c.get('text'))[:80]}",
                }
            )
    return issues
