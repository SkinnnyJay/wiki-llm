"""Build wiki-data.json and copy static site into wiki/.og/."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from lib.paths import plugin_root

WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
MDLINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def _simple_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Minimal YAML frontmatter without PyYAML dependency."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip().splitlines()
    fm: dict[str, Any] = {}
    for line in raw:
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    body = text[end + 4 :].lstrip("\n")
    return fm, body


def _title(fm: dict[str, Any], body: str, rel: str) -> str:
    if fm.get("title"):
        return str(fm["title"])
    m = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return Path(rel).stem


def collect_wiki(vault: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    wiki = vault / "wiki"
    if not wiki.is_dir():
        return {"nodes": [], "edges": [], "ledger": []}
    base_url = (cfg.get("viewer") or {}).get("og_base_url") or ""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for path in sorted(wiki.rglob("*.md")):
        if ".og" in path.parts:
            continue
        rel = path.relative_to(wiki).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, body = _simple_frontmatter(text)
        title = _title(fm, body, rel)
        node_id = rel
        url = f"{base_url.rstrip('/')}/{rel}" if base_url else ""
        nodes.append(
            {
                "id": node_id,
                "path": rel,
                "title": title,
                "markdown": text,
                "og": {"title": title, "description": body[:280].replace("\n", " "), "url": url},
            }
        )
        for m in WIKILINK.finditer(body):
            target = m.group(1).strip()
            tgt = target if target.endswith(".md") else f"{target}.md"
            edges.append({"source": node_id, "target": tgt, "kind": "wikilink"})
        for m in MDLINK.finditer(body):
            href = m.group(2).strip()
            if href.endswith(".md") and not href.startswith("http"):
                edges.append({"source": node_id, "target": href.lstrip("./"), "kind": "mdlink"})
    return {"nodes": nodes, "edges": edges, "ledger": []}


def wiki_data_meta(vault: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    viewer = cfg.get("viewer") or {}
    persona = cfg.get("persona") or {}
    return {
        "vaultAbsolutePath": str(vault.resolve()),
        "openFileScheme": viewer.get("open_file_scheme") or "file",
        "ogBaseUrl": viewer.get("og_base_url") or "",
        "personaName": str(persona.get("name") or "Gennie"),
    }


def site_is_stale(vault: Path) -> bool:
    """Return True if any wiki/*.md is newer than wiki/.og/wiki-data.json."""
    data_json = vault / "wiki" / ".og" / "wiki-data.json"
    if not data_json.exists():
        return True
    ref_mtime = data_json.stat().st_mtime
    wiki = vault / "wiki"
    if not wiki.is_dir():
        return False
    for md in wiki.rglob("*.md"):
        if ".og" in md.parts:
            continue
        if md.stat().st_mtime > ref_mtime:
            return True
    return False


def build_site(vault: Path, cfg: dict[str, Any]) -> Path:
    viewer = cfg.get("viewer") or {}
    if viewer.get("enabled") is False:
        print("viewer.enabled is false; skipping build-site.")
        return vault / "wiki" / ".og"
    og = vault / "wiki" / ".og"
    og.mkdir(parents=True, exist_ok=True)
    data = collect_wiki(vault, cfg)
    data["meta"] = wiki_data_meta(vault, cfg)
    # Optional git ledger in wiki-data
    git_cfg = cfg.get("git") or {}
    if git_cfg.get("enabled") and (vault / ".git").is_dir():
        try:
            from lib import git as vgit

            commits = vgit.git_log_json(vault, cfg, n=15)
            data["ledger"] = commits
        except Exception:
            data["ledger"] = []
    (og / "wiki-data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tpl = plugin_root() / "templates" / "site"
    if tpl.is_dir():
        for f in tpl.iterdir():
            if f.name == "README.md" or not f.is_file():
                continue
            dest = og / f.name
            shutil.copy2(f, dest)
    return og
