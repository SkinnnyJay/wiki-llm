"""Knowledge diff: wiki + KG changes since a git ref or previous snapshot."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def _git(vault: Path, *args: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(vault),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def wiki_paths_changed(vault: Path, since: str = "HEAD~1") -> dict[str, Any]:
    """List wiki/ and .kg* paths changed since git ref (requires vault git)."""
    code, _ = _git(vault, "rev-parse", "--is-inside-work-tree")
    if code != 0:
        return {
            "ok": False,
            "error": "vault is not a git repository (enable git.init_on_setup or git init)",
            "since": since,
            "changed": [],
        }
    code, out = _git(
        vault,
        "diff",
        "--name-status",
        since,
        "--",
        "wiki/",
        ".kg.json",
        ".kg.sqlite3",
        "raw/.tags.json",
    )
    changed: list[dict[str, str]] = []
    if code == 0:
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                changed.append({"status": parts[0], "path": parts[1]})
            else:
                changed.append({"status": "?", "path": line})
    else:
        # First commit / bad ref — fallback to listing wiki
        wiki = vault / "wiki"
        if wiki.is_dir():
            for p in wiki.rglob("*.md"):
                if ".og" in p.parts:
                    continue
                changed.append(
                    {
                        "status": "A",
                        "path": p.relative_to(vault).as_posix(),
                    }
                )
    return {
        "ok": True,
        "since": since,
        "changed": changed,
        "count": len(changed),
    }


def kg_snapshot_stats(vault: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    from lib.knowledge_graph import get_kg_backend

    kg = get_kg_backend(vault, cfg)
    return kg.stats()


def knowledge_diff(
    vault: Path,
    cfg: dict[str, Any],
    *,
    since: str = "HEAD~1",
) -> dict[str, Any]:
    paths = wiki_paths_changed(vault, since=since)
    stats = kg_snapshot_stats(vault, cfg)
    return {
        "ok": paths.get("ok", False),
        "since": since,
        "wiki_changed": paths.get("changed", []),
        "wiki_changed_count": paths.get("count", 0),
        "kg_stats": stats,
        "error": paths.get("error"),
    }


def format_diff_text(report: dict[str, Any]) -> str:
    lines = [f"Knowledge diff since {report.get('since')}:"]
    if report.get("error"):
        lines.append(f"  note: {report['error']}")
    for ch in report.get("wiki_changed") or []:
        lines.append(f"  {ch.get('status', '?')}\t{ch.get('path')}")
    if not report.get("wiki_changed"):
        lines.append("  (no wiki/.kg path changes)")
    kg = report.get("kg_stats") or {}
    if kg:
        lines.append(
            "  kg: "
            + ", ".join(f"{k}={v}" for k, v in kg.items() if not str(k).startswith("_"))
        )
    return "\n".join(lines) + "\n"


def write_diff_json(vault: Path, report: dict[str, Any]) -> Path:
    out = vault / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "knowledge-diff.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path
