"""On-demand D3 graph bundles (link view + knowledge / component clustering)."""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.paths import plugin_root
from lib.sitegen import collect_wiki


def _valid_edges(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = {n["id"] for n in nodes}
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s not in ids or t not in ids or s == t:
            continue
        key = tuple(sorted((s, t)))
        if key in seen:
            continue
        seen.add(key)
        out.append({"source": s, "target": t, "kind": e.get("kind", "link")})
    return out


def _undirected_degrees(node_ids: set[str], edges: list[dict[str, Any]]) -> dict[str, int]:
    deg = {n: 0 for n in node_ids}
    for e in edges:
        deg[e["source"]] = deg.get(e["source"], 0) + 1
        deg[e["target"]] = deg.get(e["target"], 0) + 1
    return deg


def _connected_components(node_ids: set[str], pairs: list[tuple[str, str]]) -> list[list[str]]:
    parent = {n: n for n in node_ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if ra < rb:
            parent[rb] = ra
        else:
            parent[ra] = rb

    for a, b in pairs:
        if a in parent and b in parent:
            union(a, b)

    buckets: dict[str, list[str]] = defaultdict(list)
    for n in node_ids:
        buckets[find(n)].append(n)
    groups = [sorted(members) for members in buckets.values()]
    groups.sort(key=lambda g: (-len(g), g[0]))
    return groups


def _cluster_metadata(
    groups: list[list[str]],
    id_to_title: dict[str, str],
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    node_cluster: dict[str, int] = {}
    summaries: list[dict[str, Any]] = []
    for idx, members in enumerate(groups):
        titles = [id_to_title.get(m, m) for m in members[:5]]
        summaries.append(
            {
                "id": idx,
                "size": len(members),
                "sample_title": titles[0] if titles else members[0],
                "titles_preview": titles,
            }
        )
        for m in members:
            node_cluster[m] = idx
    return node_cluster, summaries


def _collect_tag_edges(vault: Path, cfg: dict) -> tuple[list[dict], list[dict]]:
    """
    Build extra nodes and edges from raw/.tags.json.
    Respects graph config: tag_edges, include_raw_nodes, curated_by_edges.
    Returns (raw_nodes, tag_edges) — both empty if tag_edges disabled.
    """
    import json as _json

    graph_cfg = cfg.get("graph") or {}
    if not graph_cfg.get("tag_edges", True):
        return [], []

    include_raw = graph_cfg.get("include_raw_nodes", True)
    include_curated = graph_cfg.get("curated_by_edges", True)

    tags_path = vault / "raw" / ".tags.json"
    if not tags_path.exists():
        return [], []
    try:
        index = _json.loads(tags_path.read_text(encoding="utf-8"))
    except Exception:
        return [], []

    all_raw: set[str] = set()
    for paths in index.values():
        all_raw.update(paths)

    raw_nodes = (
        [{"id": p, "path": p, "title": Path(p).stem, "kind": "raw"} for p in sorted(all_raw)]
        if include_raw
        else []
    )

    edges: list[dict] = []
    # Tag co-occurrence
    for tag, paths in index.items():
        for i, a in enumerate(paths):
            for b in paths[i + 1 :]:
                edges.append({"source": a, "target": b, "kind": f"tag:{tag}"})

    # curated_by: raw/ → wiki/ page for matching tag
    if include_curated:
        wiki_dir = vault / "wiki"
        if wiki_dir.exists():
            for tag, paths in index.items():
                for candidate in [wiki_dir / f"{tag}.md", wiki_dir / "topics" / f"{tag}.md"]:
                    if candidate.exists():
                        wiki_id = candidate.relative_to(wiki_dir).as_posix()
                        for raw_path in paths:
                            edges.append({"source": raw_path, "target": wiki_id, "kind": "curated_by"})
                        break

    return raw_nodes, edges


def build_graph_bundle(vault: Path, cfg: dict[str, Any], out_dir: Path, mode: str) -> Path:
    """
    Write graph-data.json + static D3 assets to out_dir.
    mode: \"links\" — force layout by connectivity only; \"knowledge\" — color by connected component (link cluster).
    """
    if mode not in ("links", "knowledge"):
        raise ValueError(mode)
    raw = collect_wiki(vault, cfg)
    nodes_full = raw.get("nodes") or []

    # Merge raw/ nodes from tag index (before id_to_title so tag edges survive _valid_edges)
    tag_raw_nodes, tag_edges = _collect_tag_edges(vault, cfg)
    existing_ids = {n["id"] for n in nodes_full}
    nodes_full = nodes_full + [n for n in tag_raw_nodes if n["id"] not in existing_ids]

    all_wiki_edges = (raw.get("edges") or []) + tag_edges
    edges = _valid_edges(nodes_full, all_wiki_edges)

    id_to_title = {n["id"]: str(n.get("title") or n["id"]) for n in nodes_full}
    slim: list[dict[str, Any]] = [
        {"id": n["id"], "path": n["path"], "title": id_to_title[n["id"]]} for n in nodes_full
    ]
    node_ids = {n["id"] for n in slim}
    deg = _undirected_degrees(node_ids, edges)
    pairs = [(e["source"], e["target"]) for e in edges]

    clusters: list[dict[str, Any]] = []
    if mode == "knowledge" and slim:
        groups = _connected_components(node_ids, pairs)
        mapping, clusters = _cluster_metadata(groups, id_to_title)
        for n in slim:
            n["cluster"] = mapping[n["id"]]
            n["degree"] = deg.get(n["id"], 0)
    else:
        for n in slim:
            n["cluster"] = 0
            n["degree"] = deg.get(n["id"], 0)

    pname = str((cfg.get("persona") or {}).get("name") or "Gennie")
    payload: dict[str, Any] = {
        "meta": {
            "mode": mode,
            "persona_name": pname,
            "title": "Wiki link graph" if mode == "links" else "Knowledge clusters (linked components)",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "vault_path": str(vault.resolve()),
            "node_count": len(slim),
            "edge_count": len(edges),
        },
        "nodes": slim,
        "edges": edges,
        "clusters": clusters,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "graph-data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    tpl = plugin_root() / "templates" / "graph-bundle"
    if not tpl.is_dir():
        raise FileNotFoundError(f"Missing graph template: {tpl}")
    for f in tpl.iterdir():
        if f.suffix.lower() in (".html", ".js", ".css", ".svg", ".png") and f.is_file():
            shutil.copy2(f, out_dir / f.name)
    return out_dir
