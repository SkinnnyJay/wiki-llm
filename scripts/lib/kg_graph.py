"""Graph traversal helpers for knowledge triples (JSON or SQLite backends)."""
from __future__ import annotations

from collections import deque
from typing import Any


def _active_triples(triples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t for t in triples if not t.get("valid_until")]


def traverse_bfs_triples(
    triples: list[dict[str, Any]],
    start: str,
    *,
    max_depth: int = 2,
) -> list[dict[str, Any]]:
    """Collect triples reachable within ``max_depth`` hops from ``start`` (undirected)."""
    active = _active_triples(triples)
    if not start or max_depth < 0:
        return []
    seen_t: set[str] = set()
    seen_e = {start}
    q: deque[tuple[str, int]] = deque([(start, 0)])
    out: list[dict[str, Any]] = []
    while q:
        ent, d = q.popleft()
        if d > max_depth:
            continue
        for t in active:
            tid = str(t.get("id", ""))
            other: str | None = None
            if t.get("s") == ent:
                other = str(t.get("o", ""))
            elif t.get("o") == ent:
                other = str(t.get("s", ""))
            else:
                continue
            if tid and tid not in seen_t:
                seen_t.add(tid)
                out.append(t)
            if other and other not in seen_e and d < max_depth:
                seen_e.add(other)
                q.append((other, d + 1))
    return out


def find_tunnels_triples(triples: list[dict[str, Any]], room: str) -> list[dict[str, Any]]:
    """Return active triples that touch ``room`` as subject or object (palace tunnel / room bridge)."""
    r = room.strip()
    if not r:
        return []
    return [
        t
        for t in _active_triples(triples)
        if t.get("s") == r or t.get("o") == r
    ]


def shortest_path_triples(
    triples: list[dict[str, Any]],
    a: str,
    b: str,
    *,
    max_depth: int = 12,
) -> list[dict[str, Any]] | None:
    """Return triples on a shortest path from entity ``a`` to ``b`` (undirected), or None."""
    active = _active_triples(triples)
    if a == b:
        return []
    q: deque[tuple[str, list[dict[str, Any]]]] = deque([(a, [])])
    visited = {a}
    while q:
        ent, path = q.popleft()
        if len(path) >= max_depth:
            continue
        for t in active:
            other: str | None = None
            if t.get("s") == ent:
                other = str(t.get("o", ""))
            elif t.get("o") == ent:
                other = str(t.get("s", ""))
            else:
                continue
            if not other:
                continue
            npath = path + [t]
            if other == b:
                return npath
            if other not in visited:
                visited.add(other)
                q.append((other, npath))
    return None
