"""Pluggable knowledge graph: JSON file (default) with Protocol for future SQLite."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Protocol

from lib.config_loader import resolve_storage_path


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class KGBackend(Protocol):
    def add_triple(
        self, subject: str, predicate: str, object_: str,
        *, valid_from: str | None = None, source: str | None = None,
    ) -> str: ...

    def query_entity(self, entity: str, *, as_of: str | None = None) -> list[dict[str, Any]]: ...

    def invalidate(
        self, subject: str, predicate: str, object_: str,
        *, ended: str | None = None,
    ) -> bool: ...

    def timeline(self, entity: str | None = None) -> list[dict[str, Any]]: ...

    def stats(self) -> dict[str, Any]: ...

    def rebuild(self, vault: Path) -> dict[str, Any]: ...


def rebuild_knowledge_graph(
    vault: Path, cfg: dict[str, Any], *, backend: KGBackend | None = None
) -> dict[str, Any]:
    """Rebuild the configured graph, returning a disabled marker when unavailable."""
    if not (cfg.get("knowledge_graph") or {}).get("enabled", True):
        return {"disabled": True}
    return (backend or get_kg_backend(vault, cfg)).rebuild(vault)


# ---------------------------------------------------------------------------
# JSON file KG (default — zero deps)
# ---------------------------------------------------------------------------

_KG_FILENAME = ".kg.json"


def _kg_path(vault: Path, cfg: dict[str, Any] | None = None) -> Path:
    if cfg:
        return resolve_storage_path(vault, cfg, "kg_db")
    return vault / _KG_FILENAME


def _load_kg(path: Path) -> dict[str, Any]:
    from lib.json_index import CorruptIndexError, load_json_object

    if not path.exists():
        return {"entities": {}, "triples": []}
    try:
        data = load_json_object(path, default_if_missing={"entities": {}, "triples": []})
    except CorruptIndexError:
        raise
    if "entities" not in data:
        data["entities"] = {}
    if "triples" not in data:
        data["triples"] = []
    if not isinstance(data["entities"], dict) or not isinstance(data["triples"], list):
        from lib.json_index import quarantine_corrupt, CorruptIndexError as CIE

        quarantine_corrupt(path, ValueError("invalid kg shape"))
        raise CIE(path, "invalid kg shape")
    return data


def _save_kg(path: Path, data: dict[str, Any]) -> None:
    from lib.json_index import atomic_write_json

    atomic_write_json(path, data)


def _triple_id(s: str, p: str, o: str) -> str:
    raw = f"{s}|{p}|{o}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


class JSONFileKG:
    def __init__(self, vault: Path, cfg: dict[str, Any] | None = None):
        import threading

        self._vault = vault
        self._cfg = cfg or {}
        self._path = _kg_path(vault, self._cfg)
        self._metrics: Any = None
        self._lock = threading.RLock()

    def add_triple(
        self, subject: str, predicate: str, object_: str,
        *, valid_from: str | None = None, source: str | None = None,
    ) -> str:
        from lib.entity_aliases import canonicalize_triple
        from lib.kg_ontology import ontology_error

        subject, predicate, object_ = canonicalize_triple(
            subject, predicate, object_, self._cfg
        )
        err = ontology_error(predicate, self._cfg)
        if err:
            raise ValueError(err)
        with self._lock:
            data = _load_kg(self._path)
            tid = _triple_id(subject, predicate, object_)

            for t in data["triples"]:
                if t.get("id") == tid and not t.get("valid_until"):
                    return tid

            triple: dict[str, Any] = {
                "id": tid,
                "s": subject,
                "p": predicate,
                "o": object_,
                "valid_from": valid_from or _today(),
            }
            if source:
                triple["source"] = source

            data["triples"].append(triple)

            for entity in (subject, object_):
                if entity not in data["entities"]:
                    data["entities"][entity] = {"first_seen": valid_from or _today()}

            _save_kg(self._path, data)
            if self._metrics:
                self._metrics.record("kg.add_triple", 1, meta={"subject": subject, "predicate": predicate})
            return tid

    def query_entity(self, entity: str, *, as_of: str | None = None) -> list[dict[str, Any]]:
        from lib.entity_aliases import canonicalize_entity

        entity = canonicalize_entity(entity, self._cfg)
        t0 = time.monotonic()
        data = _load_kg(self._path)
        results: list[dict[str, Any]] = []
        for t in data["triples"]:
            if t["s"] != entity and t["o"] != entity:
                continue
            if as_of:
                vf = t.get("valid_from", "")
                vu = t.get("valid_until")
                if vf and vf > as_of:
                    continue
                if vu and vu <= as_of:
                    continue
            elif t.get("valid_until"):
                continue
            results.append(t)
        if self._metrics:
            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
            self._metrics.record("kg.query_ms", elapsed_ms, meta={"entity": entity, "results": len(results)})
        return results

    def invalidate(
        self, subject: str, predicate: str, object_: str,
        *, ended: str | None = None,
    ) -> bool:
        from lib.entity_aliases import canonicalize_triple

        subject, predicate, object_ = canonicalize_triple(
            subject, predicate, object_, self._cfg
        )
        with self._lock:
            data = _load_kg(self._path)
            tid = _triple_id(subject, predicate, object_)
            found = False
            for t in data["triples"]:
                if t.get("id") == tid and not t.get("valid_until"):
                    t["valid_until"] = ended or _today()
                    found = True
            if found:
                _save_kg(self._path, data)
            return found

    def timeline(self, entity: str | None = None) -> list[dict[str, Any]]:
        data = _load_kg(self._path)
        triples = data["triples"]
        if entity:
            from lib.entity_aliases import canonicalize_entity

            entity = canonicalize_entity(entity, self._cfg)
            triples = [t for t in triples if t["s"] == entity or t["o"] == entity]
        return sorted(triples, key=lambda t: t.get("valid_from", ""))

    def stats(self) -> dict[str, Any]:
        data = _load_kg(self._path)
        total = len(data["triples"])
        active = sum(1 for t in data["triples"] if not t.get("valid_until"))
        predicates: set[str] = set()
        for t in data["triples"]:
            predicates.add(t["p"])
        return {
            "backend": "json",
            "entities": len(data["entities"]),
            "triples_total": total,
            "triples_active": active,
            "triples_expired": total - active,
            "predicates": sorted(predicates),
            "kg_path": str(self._path),
        }

    def rebuild(self, vault: Path) -> dict[str, Any]:
        """Rebuild KG from vault files: extract entities from wikilinks + frontmatter tags."""
        from lib.search import _walk_vault_md, _parse_frontmatter, _tags_for_file

        with self._lock:
            data = _load_kg(self._path)
            added = 0

            existing_ids = {t["id"] for t in data["triples"]}

            wikilink_re = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

            from lib.entity_aliases import canonicalize_entity

            for rel, text in _walk_vault_md(vault):
                fm, body = _parse_frontmatter(text)
                tags = _tags_for_file(fm)
                page_name = canonicalize_entity(Path(rel).stem, self._cfg)

                for tag in tags:
                    tag_c = canonicalize_entity(str(tag), self._cfg)
                    tid = _triple_id(page_name, "tagged", tag_c)
                    if tid not in existing_ids:
                        data["triples"].append({
                            "id": tid, "s": page_name, "p": "tagged", "o": tag_c,
                            "valid_from": _today(), "source": rel,
                        })
                        existing_ids.add(tid)
                        added += 1
                    for entity in (page_name, tag_c):
                        if entity not in data["entities"]:
                            data["entities"][entity] = {"first_seen": _today()}

                for m in wikilink_re.finditer(body):
                    target = canonicalize_entity(m.group(1).strip(), self._cfg)
                    if not target:
                        continue
                    tid = _triple_id(page_name, "links_to", target)
                    if tid not in existing_ids:
                        data["triples"].append({
                            "id": tid, "s": page_name, "p": "links_to", "o": target,
                            "valid_from": _today(), "source": rel,
                        })
                        existing_ids.add(tid)
                        added += 1
                    for entity in (page_name, target):
                        if entity not in data["entities"]:
                            data["entities"][entity] = {"first_seen": _today()}

                kg_cfg = (self._cfg.get("knowledge_graph") or {}) if self._cfg else {}
                if kg_cfg.get("entity_detection", True):
                    from lib.entity_detector import extract_entities

                    for ent in extract_entities(body, cfg=self._cfg or {}):
                        ent_c = canonicalize_entity(ent, self._cfg)
                        if ent_c == page_name:
                            continue
                        tid = _triple_id(page_name, "mentions", ent_c)
                        if tid not in existing_ids:
                            data["triples"].append({
                                "id": tid, "s": page_name, "p": "mentions", "o": ent_c,
                                "valid_from": _today(), "source": rel,
                            })
                            existing_ids.add(tid)
                            added += 1
                        for e2 in (page_name, ent_c):
                            if e2 not in data["entities"]:
                                data["entities"][e2] = {"first_seen": _today()}

            _save_kg(self._path, data)
            return {"added": added, "total_triples": len(data["triples"]), "entities": len(data["entities"])}

    def _all_triples(self) -> list[dict[str, Any]]:
        data = _load_kg(self._path)
        return list(data["triples"])

    def traverse_bfs(self, start: str, *, max_depth: int = 2) -> list[dict[str, Any]]:
        from lib.kg_graph import traverse_bfs_triples

        return traverse_bfs_triples(self._all_triples(), start, max_depth=max_depth)

    def find_tunnels(self, room: str) -> list[dict[str, Any]]:
        from lib.kg_graph import find_tunnels_triples

        return find_tunnels_triples(self._all_triples(), room)

    def find_connection_path(
        self, a: str, b: str, *, max_depth: int = 12
    ) -> list[dict[str, Any]] | None:
        from lib.kg_graph import shortest_path_triples

        return shortest_path_triples(self._all_triples(), a, b, max_depth=max_depth)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_kg_backend(vault: Path, cfg: dict[str, Any]) -> KGBackend:
    backend_name = (cfg.get("knowledge_graph") or {}).get("backend", "json")
    if backend_name == "sqlite":
        try:
            from lib.kg_sqlite import SQLiteKG
            return SQLiteKG(vault, cfg)
        except ImportError:
            pass
    return JSONFileKG(vault, cfg)
