"""Per-session memory files under raw/memory/<session-id>.md."""

from __future__ import annotations

import datetime
import fnmatch
import json
import re
from pathlib import Path
from typing import Any

from lib.search import SearchResult, get_search_backend

_ROUNDS_MARKER = "<!-- llm-wiki-memory:rounds -->"
_FM_END = re.compile(r"^---\s*$", re.M)
_SECTION_COMPACT = "## Compact summary"
_SECTION_AGENT = "## Agent notes"


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def memory_dir(vault: Path, cfg: dict[str, Any]) -> Path:
    mem = cfg.get("memory") or {}
    rel = (mem.get("dir") or "raw/memory").strip().strip("/")
    return vault / rel


def memory_enabled(cfg: dict[str, Any]) -> bool:
    return bool((cfg.get("memory") or {}).get("enabled"))


def sanitize_session_id(session_id: str) -> str:
    s = session_id.strip()
    if not s:
        return "unknown"
    out = []
    for c in s:
        if c.isalnum() or c in "._-":
            out.append(c)
        else:
            out.append("_")
    return "".join(out) or "unknown"


def resolve_current_session(vault: Path) -> str:
    p = vault / ".current-session"
    if not p.is_file():
        raise FileNotFoundError("No .current-session in vault — run from Claude Code hooks or pass --session-id")
    sid = p.read_text(encoding="utf-8", errors="replace").strip()
    if not sid:
        raise ValueError(".current-session is empty")
    return sid


def resolve_session_arg(
    vault: Path,
    *,
    session_id: str | None,
    current: bool,
) -> str:
    if current:
        return resolve_current_session(vault)
    if session_id:
        return session_id.strip()
    raise ValueError("Pass --session-id or --current")


def _parse_simple_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not m:
        return {}, text
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    body = text[m.end() :]
    return fm, body


def _dump_frontmatter(fm: dict[str, str]) -> str:
    lines = ["---"]
    order = ("session_id", "created", "updated", "tags", "rounds", "meta_json")
    seen: set[str] = set()
    for k in order:
        if k in fm:
            lines.append(f"{k}: {fm[k]}")
            seen.add(k)
    for k in sorted(fm.keys()):
        if k not in seen:
            lines.append(f"{k}: {fm[k]}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _merge_tags(existing: str, new_tags: list[str] | None) -> str:
    cur = {t.strip() for t in existing.replace(",", " ").split() if t.strip()}
    if new_tags:
        cur.update(t.strip() for t in new_tags if t.strip())
    return ", ".join(sorted(cur))


def _session_paths(mem_root: Path) -> list[Path]:
    if not mem_root.is_dir():
        return []
    return sorted(mem_root.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)


def _match_session_filter(
    stem: str,
    session_id: str | None,
) -> bool:
    if not session_id:
        return True
    parts = [p.strip() for p in session_id.split(",") if p.strip()]
    for pat in parts:
        if fnmatch.fnmatch(stem, pat) or stem == pat:
            return True
    return False


def _fm_tags(fm: dict[str, str]) -> list[str]:
    raw = fm.get("tags", "") or fm.get("llm_wiki_tags", "")
    return [t.strip() for t in raw.replace(",", " ").split() if t.strip()]


def _resolve_sessions(
    vault: Path,
    cfg: dict[str, Any],
    *,
    session_id: str | None = None,
    tag: str | None = None,
) -> list[Path]:
    mem_root = memory_dir(vault, cfg)
    out: list[Path] = []
    for p in _session_paths(mem_root):
        stem = p.stem
        if not _match_session_filter(stem, session_id):
            continue
        if tag:
            text = p.read_text(encoding="utf-8", errors="replace")
            fm, _ = _parse_simple_frontmatter(text)
            tags = _fm_tags(fm)
            if tag not in tags:
                continue
        out.append(p)
    return out


def memory_save(
    vault: Path,
    cfg: dict[str, Any],
    session_id: str,
    *,
    summary: str | None = None,
    compact_summary: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    if not memory_enabled(cfg):
        raise RuntimeError("memory.enabled is false in config")
    sid = sanitize_session_id(session_id)
    mem_root = memory_dir(vault, cfg)
    mem_root.mkdir(parents=True, exist_ok=True)
    path = mem_root / f"{sid}.md"
    now = _utc_now()
    if path.is_file():
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, body = _parse_simple_frontmatter(text)
    else:
        fm, body = {}, ""
    fm.setdefault("session_id", sid)
    fm.setdefault("created", now)
    fm["updated"] = now
    if tags:
        fm["tags"] = _merge_tags(fm.get("tags", ""), tags)
    if metadata is not None:
        fm["meta_json"] = json.dumps(metadata, ensure_ascii=False)
    # Body: ensure title
    if not body.strip():
        body = f"# Session {sid}\n\n{_SECTION_COMPACT}\n\n\n{_SECTION_AGENT}\n\n\n{_ROUNDS_MARKER}\n"
    elif _ROUNDS_MARKER not in body:
        body = body.rstrip() + f"\n\n{_ROUNDS_MARKER}\n"
    if compact_summary is not None:
        body = _replace_section(body, _SECTION_COMPACT, compact_summary.strip())
    if summary is not None:
        body = _replace_section(body, _SECTION_AGENT, summary.strip())
    # Re-count rounds
    rounds = len(re.findall(r"\*\*[^*]+\*\* \| Round \d+", body))
    fm["rounds"] = str(rounds)
    out_text = _dump_frontmatter(fm) + body
    path.write_text(out_text, encoding="utf-8")
    auto_prune_if_needed(vault, cfg)
    return path


def _replace_section(body: str, heading: str, content: str) -> str:
    if heading not in body:
        if _ROUNDS_MARKER in body:
            idx = body.index(_ROUNDS_MARKER)
            insert = f"{heading}\n\n{content}\n\n"
            return body[:idx] + insert + body[idx:]
        return body.rstrip() + f"\n\n{heading}\n\n{content}\n"
    i = body.index(heading) + len(heading)
    rest = body[i:]
    m = re.search(r"\n(?:## |<!-- )", rest)
    if m:
        return body[:i] + f"\n\n{content}\n" + rest[m.start() :]
    return body[:i] + f"\n\n{content}\n"


def memory_log_round(
    vault: Path,
    cfg: dict[str, Any],
    session_id: str,
    *,
    message_preview: str | None = None,
) -> Path:
    if not memory_enabled(cfg):
        raise RuntimeError("memory.enabled is false in config")
    sid = sanitize_session_id(session_id)
    mem_root = memory_dir(vault, cfg)
    mem_root.mkdir(parents=True, exist_ok=True)
    path = mem_root / f"{sid}.md"
    preview = (message_preview or "").strip()
    if len(preview) > 500:
        preview = preview[:497] + "..."
    now = _utc_now()
    if path.is_file():
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, body = _parse_simple_frontmatter(text)
    else:
        fm, body = {}, ""
    fm.setdefault("session_id", sid)
    fm.setdefault("created", now)
    fm["updated"] = now
    # Count rounds from frontmatter
    try:
        n = int(fm.get("rounds", "0") or "0")
    except ValueError:
        n = 0
    n += 1
    fm["rounds"] = str(n)
    if not body.strip():
        body = f"# Session {sid}\n\n{_SECTION_COMPACT}\n\n\n{_SECTION_AGENT}\n\n\n{_ROUNDS_MARKER}\n"
    elif _ROUNDS_MARKER not in body:
        body = body.rstrip() + f"\n\n{_ROUNDS_MARKER}\n"
    block = f"\n---\n\n**{now}** | Round {n}\n\n{preview}\n"
    if _ROUNDS_MARKER in body:
        body = body.replace(_ROUNDS_MARKER, _ROUNDS_MARKER + block, 1)
    else:
        body = body.rstrip() + block
    out_text = _dump_frontmatter(fm) + body
    path.write_text(out_text, encoding="utf-8")
    auto_prune_if_needed(vault, cfg)
    return path


def memory_list(
    vault: Path,
    cfg: dict[str, Any],
    *,
    session_id: str | None = None,
    tag: str | None = None,
) -> list[dict[str, Any]]:
    mem_root = memory_dir(vault, cfg)
    rows: list[dict[str, Any]] = []
    for p in _resolve_sessions(vault, cfg, session_id=session_id, tag=tag):
        text = p.read_text(encoding="utf-8", errors="replace")
        fm, _ = _parse_simple_frontmatter(text)
        st = p.stat()
        rows.append(
            {
                "session_id": p.stem,
                "path": p.relative_to(vault).as_posix(),
                "created": fm.get("created", ""),
                "updated": fm.get("updated", ""),
                "tags": _fm_tags(fm),
                "rounds": int(fm.get("rounds", "0") or "0"),
                "mtime": st.st_mtime,
            }
        )
    rows.sort(key=lambda r: r.get("mtime", 0), reverse=True)
    return rows


def memory_show(vault: Path, cfg: dict[str, Any], session_id: str) -> str:
    sid = sanitize_session_id(session_id)
    path = memory_dir(vault, cfg) / f"{sid}.md"
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return path.read_text(encoding="utf-8", errors="replace")


def memory_recall(
    vault: Path,
    cfg: dict[str, Any],
    query: str,
    *,
    session_id: str | None = None,
    tag: str | None = None,
    limit: int = 5,
) -> list[SearchResult]:
    backend = get_search_backend(vault, cfg)
    # Widen limit for post-filter
    raw = backend.search(query, limit=limit * 4, tag=tag, scope="memory")
    if not session_id:
        return raw[:limit]
    stems = set()
    for part in [p.strip() for p in session_id.split(",") if p.strip()]:
        for p in _session_paths(memory_dir(vault, cfg)):
            if fnmatch.fnmatch(p.stem, part) or p.stem == part:
                stems.add(p.stem)
    out: list[SearchResult] = []
    for r in raw:
        for stem in stems:
            if r.path.startswith(f"raw/memory/{stem}"):
                out.append(r)
                break
    return out[:limit]


def memory_prune(
    vault: Path,
    cfg: dict[str, Any],
    *,
    session_id: str | None = None,
    tag: str | None = None,
    older_than_days: int | None = None,
    keep: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete session memory files. Requires at least one of: older_than_days, keep, or session_id."""
    mem_root = memory_dir(vault, cfg)
    if not mem_root.is_dir():
        return {"deleted": [], "dry_run": dry_run}
    paths = _resolve_sessions(vault, cfg, session_id=session_id, tag=tag)
    if not paths:
        paths = _session_paths(mem_root)
    to_delete: list[Path] = []
    if older_than_days is not None:
        cutoff = datetime.datetime.now(datetime.timezone.utc).timestamp() - older_than_days * 86400
        pool = _resolve_sessions(vault, cfg, session_id=session_id, tag=tag) or _session_paths(mem_root)
        to_delete = [p for p in pool if p.stat().st_mtime < cutoff]
    elif keep is not None and keep >= 0:
        pool = _resolve_sessions(vault, cfg, session_id=session_id, tag=tag) or _session_paths(mem_root)
        newest_first = sorted(pool, key=lambda p: p.stat().st_mtime, reverse=True)
        if len(newest_first) > keep:
            keep_set = set(newest_first[:keep])
            to_delete = [p for p in pool if p not in keep_set]
    elif session_id or tag:
        to_delete = list(paths)
    else:
        raise ValueError("memory prune: specify --older-than, --keep, or --session-id / --tag")
    deleted: list[str] = []
    for p in to_delete:
        rel = p.relative_to(vault).as_posix()
        if not dry_run:
            p.unlink(missing_ok=True)
        deleted.append(rel)
    return {"deleted": deleted, "dry_run": dry_run}


def auto_prune_if_needed(vault: Path, cfg: dict[str, Any]) -> None:
    mem = cfg.get("memory") or {}
    max_s = mem.get("max_sessions")
    if not isinstance(max_s, int) or max_s <= 0:
        return
    mem_root = memory_dir(vault, cfg)
    paths = sorted(_session_paths(mem_root), key=lambda p: p.stat().st_mtime)
    if len(paths) <= max_s:
        return
    to_delete = paths[: len(paths) - max_s]
    for p in to_delete:
        p.unlink(missing_ok=True)
