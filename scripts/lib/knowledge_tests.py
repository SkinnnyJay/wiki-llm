"""Knowledge regression tests: assert compiled wiki still contains claims."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_knowledge_tests(path: Path) -> list[dict[str, Any]]:
    """Load YAML-ish or JSON test file. Prefer JSON; simple YAML subset if .yml."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".json",):
        data = json.loads(text)
    else:
        # Minimal YAML: list of {id, contains} maps — prefer JSON for CI
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(text)
        except Exception:
            data = json.loads(text)
    if isinstance(data, dict) and "tests" in data:
        data = data["tests"]
    if not isinstance(data, list):
        raise ValueError("knowledge tests must be a list or {tests: [...]}")
    return [t for t in data if isinstance(t, dict)]


def run_knowledge_tests(vault: Path, tests: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Each test: {id, path?: wiki-relative, contains?: str|list, absent?: str|list}
    Default path: wiki/ (search all md) if path omitted — prefer explicit path.
    """
    results: list[dict[str, Any]] = []
    failed = 0
    for t in tests:
        tid = str(t.get("id") or t.get("name") or "unnamed")
        rel = t.get("path") or t.get("page")
        contains = t.get("contains") or []
        absent = t.get("absent") or []
        if isinstance(contains, str):
            contains = [contains]
        if isinstance(absent, str):
            absent = [absent]
        body = ""
        ok = True
        detail = ""
        if rel:
            p = vault / "wiki" / str(rel)
            if not p.is_file():
                ok = False
                detail = f"missing page {rel}"
            else:
                body = p.read_text(encoding="utf-8", errors="replace")
        else:
            # Search all wiki pages
            chunks = []
            wiki = vault / "wiki"
            if wiki.is_dir():
                for p in wiki.rglob("*.md"):
                    if ".og" in p.parts:
                        continue
                    chunks.append(p.read_text(encoding="utf-8", errors="replace"))
            body = "\n".join(chunks)
        if ok:
            for needle in contains:
                if str(needle) not in body:
                    ok = False
                    detail = f"missing contains: {needle!r}"
                    break
            for needle in absent:
                if str(needle) in body:
                    ok = False
                    detail = f"found absent: {needle!r}"
                    break
        if not ok:
            failed += 1
        results.append({"id": tid, "ok": ok, "detail": detail, "path": rel})
    return {
        "ok": failed == 0,
        "failed": failed,
        "total": len(tests),
        "results": results,
    }
