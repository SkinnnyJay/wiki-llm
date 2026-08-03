"""Deterministic wiki lint for knowledge CI (orphans, links, schema, freshness)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from lib.sitegen import collect_wiki
from lib.wiki_schema import (
    SCHEMA_EXEMPT_NAMES,
    is_stale,
    parse_wiki_frontmatter,
    validate_page_schema,
)


def _wiki_md_files(wiki: Path) -> list[Path]:
    if not wiki.is_dir():
        return []
    out: list[Path] = []
    for p in wiki.rglob("*.md"):
        if ".og" in p.parts:
            continue
        out.append(p)
    return sorted(out)


def _rel_wiki_id(vault: Path, path: Path) -> str:
    try:
        return path.relative_to(vault / "wiki").as_posix()
    except ValueError:
        return path.name


def _index_link_targets(index_text: str) -> set[str]:
    indexed_targets: set[str] = set()
    for line in index_text.splitlines():
        if "[[" not in line:
            continue
        i = 0
        while True:
            a = line.find("[[", i)
            if a < 0:
                break
            b = line.find("]]", a)
            if b < 0:
                break
            raw = line[a + 2 : b].split("|", 1)[0].strip()
            if raw:
                indexed_targets.add(raw.replace("\\", "/"))
                if not raw.endswith(".md"):
                    indexed_targets.add(raw + ".md")
            i = b + 2
    return indexed_targets


def lint_vault(
    vault: Path,
    cfg: dict[str, Any],
    *,
    check_schema: bool | None = None,
    check_stale: bool = True,
    check_outputs: bool = True,
    only_pages: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run deterministic wiki health checks.

    Returns a JSON-serializable report with ok, issues[], counts.
    When ``only_pages`` is set (wiki-relative paths), restrict orphan/schema/stale
    checks to those pages (broken link scan stays vault-wide).
    """
    compile_cfg = cfg.get("compile") or {}
    if check_schema is None:
        check_schema = bool(compile_cfg.get("schema_required", False))
    require_sources = bool(compile_cfg.get("require_sources", check_schema))
    require_updated = bool(compile_cfg.get("require_updated", False))
    # None = full vault; empty list = surgical scope with zero pages (do not fall through)
    page_allow: set[str] | None = (
        None if only_pages is None else {p.replace("\\", "/") for p in only_pages}
    )

    wiki = vault / "wiki"
    issues: list[dict[str, str]] = []

    graph = collect_wiki(vault, cfg)
    ids = {n["id"] for n in graph.get("nodes", [])}
    seen_link: set[tuple[str, str]] = set()
    for e in graph.get("edges", []):
        tgt = e.get("target")
        src = e.get("source")
        if tgt not in ids:
            key = (str(src), str(tgt))
            if key not in seen_link:
                issues.append(
                    {
                        "code": "broken_wikilink",
                        "path": str(src),
                        "message": f"broken wikilink → {tgt}",
                    }
                )
                seen_link.add(key)

    index = wiki / "index.md"
    index_text = index.read_text(encoding="utf-8", errors="replace") if index.is_file() else ""
    indexed_targets = _index_link_targets(index_text)

    for path in _wiki_md_files(wiki):
        rel = _rel_wiki_id(vault, path)
        if path.name in SCHEMA_EXEMPT_NAMES:
            continue
        if page_allow is not None and rel not in page_allow and path.name not in page_allow:
            continue
        stem = path.stem
        linked = (
            rel in indexed_targets
            or path.name in indexed_targets
            or stem in indexed_targets
            or f"{stem}.md" in indexed_targets
        )
        if indexed_targets and not linked:
            issues.append(
                {
                    "code": "orphan",
                    "path": rel,
                    "message": "not linked from wiki/index.md",
                }
            )

        text = path.read_text(encoding="utf-8", errors="replace")
        fm, _ = parse_wiki_frontmatter(text)
        if check_schema:
            for msg in validate_page_schema(
                path,
                text,
                require_sources=require_sources,
                require_updated=require_updated,
            ):
                issues.append({"code": "schema", "path": rel, "message": msg})
        if check_stale and is_stale(fm, mtime=path.stat().st_mtime):
            issues.append(
                {
                    "code": "stale",
                    "path": rel,
                    "message": "past stale_after since updated/last_verified",
                }
            )
        rr = fm.get("review_required")
        if rr is True or str(rr).lower() in ("true", "1"):
            issues.append(
                {
                    "code": "review_required",
                    "path": rel,
                    "message": "review_required: true",
                }
            )

    if check_outputs and page_allow is None:
        outputs = vault / "outputs"
        if outputs.is_dir():
            wiki_names = {p.name for p in _wiki_md_files(wiki)}
            for op in outputs.rglob("*.md"):
                if op.name in wiki_names and op.name not in SCHEMA_EXEMPT_NAMES:
                    issues.append(
                        {
                            "code": "outputs_overlap",
                            "path": op.relative_to(vault).as_posix(),
                            "message": f"draft name overlaps wiki/{op.name}",
                        }
                    )

    if bool(compile_cfg.get("extract_claims", True)):
        from lib.claims import (
            extract_vault_claims,
            uncited_claim_issues,
            write_claims_index,
        )

        claims = extract_vault_claims(vault, only_pages=only_pages)
        write_claims_index(vault, claims, only_pages=only_pages)
        if bool(compile_cfg.get("fail_on_uncited_claims", False)):
            issues.extend(uncited_claim_issues(claims))

    coverage_missing: list[str] = []
    tags_path = vault / "raw" / ".tags.json"
    if tags_path.is_file() and page_allow is None:
        try:
            tags_data = json.loads(tags_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            tags_data = {}
        if isinstance(tags_data, dict):
            wiki_stems = {p.stem.lower() for p in _wiki_md_files(wiki)}
            for tag in sorted(tags_data.keys()):
                t = str(tag).strip().lower().replace(" ", "-")
                if t and t not in wiki_stems:
                    coverage_missing.append(str(tag))

    by_code: dict[str, int] = {}
    for it in issues:
        by_code[it["code"]] = by_code.get(it["code"], 0) + 1

    return {
        "ok": len(issues) == 0,
        "generated": date.today().isoformat(),
        "vault": str(vault),
        "counts": {"issues": len(issues), "by_code": by_code},
        "coverage_missing_tags": coverage_missing[:50],
        "issues": issues,
        "only_pages": list(only_pages) if only_pages is not None else None,
    }


def write_lint_report(vault: Path, report: dict[str, Any]) -> Path:
    out_dir = vault / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "lint-report.json"
    from lib.json_index import atomic_write_json

    atomic_write_json(path, report)
    return path
