"""SQLite-backed knowledge graph (stdlib sqlite3; temporal validity)."""
from __future__ import annotations

import hashlib
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.config_loader import resolve_storage_path
from lib.search import _parse_frontmatter, _tags_for_file, _walk_vault_md


def _triple_id(s: str, p: str, o: str) -> str:
    return hashlib.md5(f"{s}|{p}|{o}".encode()).hexdigest()[:12]


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


class SQLiteKG:
    def __init__(self, vault: Path, cfg: dict[str, Any] | None = None):
        self._vault = vault
        self._cfg = cfg or {}
        self._path = resolve_storage_path(vault, self._cfg, "kg_sqlite_db")
        self._metrics: Any = None
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    name TEXT PRIMARY KEY,
                    first_seen TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS triples (
                    id TEXT PRIMARY KEY,
                    s TEXT NOT NULL,
                    p TEXT NOT NULL,
                    o TEXT NOT NULL,
                    valid_from TEXT,
                    valid_until TEXT,
                    source TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_triples_s ON triples(s)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_triples_o ON triples(o)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_triples_valid ON triples(valid_from, valid_until)")

    def add_triple(
        self,
        subject: str,
        predicate: str,
        object_: str,
        *,
        valid_from: str | None = None,
        source: str | None = None,
    ) -> str:
        from lib.entity_aliases import canonicalize_triple
        from lib.kg_ontology import ontology_error

        subject, predicate, object_ = canonicalize_triple(
            subject, predicate, object_, self._cfg
        )
        err = ontology_error(predicate, self._cfg)
        if err:
            raise ValueError(err)
        tid = _triple_id(subject, predicate, object_)
        vf = valid_from or _today()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM triples WHERE id = ? AND valid_until IS NULL",
                (tid,),
            ).fetchone()
            if row:
                return tid
            conn.execute(
                """
                INSERT INTO triples (id, s, p, o, valid_from, valid_until, source)
                VALUES (?, ?, ?, ?, ?, NULL, ?)
                """,
                (tid, subject, predicate, object_, vf, source),
            )
            for entity in (subject, object_):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO entities (name, first_seen) VALUES (?, ?)
                    """,
                    (entity, vf),
                )
        if self._metrics:
            self._metrics.record("kg.add_triple", 1, meta={"subject": subject, "predicate": predicate})
        return tid

    def query_entity(self, entity: str, *, as_of: str | None = None) -> list[dict[str, Any]]:
        from lib.entity_aliases import canonicalize_entity

        entity = canonicalize_entity(entity, self._cfg)
        t0 = time.monotonic()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, s, p, o, valid_from, valid_until, source FROM triples WHERE s = ? OR o = ?",
                (entity, entity),
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            t = dict(row)
            vf = t.get("valid_from") or ""
            vu = t.get("valid_until")
            if as_of:
                if vf and vf > as_of:
                    continue
                if vu and vu <= as_of:
                    continue
            elif vu:
                continue
            results.append(
                {
                    "id": t["id"],
                    "s": t["s"],
                    "p": t["p"],
                    "o": t["o"],
                    "valid_from": vf,
                    "valid_until": vu,
                    "source": t.get("source"),
                }
            )
        if self._metrics:
            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
            self._metrics.record(
                "kg.query_ms", elapsed_ms, meta={"entity": entity, "results": len(results)}
            )
        return results

    def invalidate(
        self, subject: str, predicate: str, object_: str, *, ended: str | None = None
    ) -> bool:
        from lib.entity_aliases import canonicalize_triple

        subject, predicate, object_ = canonicalize_triple(
            subject, predicate, object_, self._cfg
        )
        tid = _triple_id(subject, predicate, object_)
        end = ended or _today()
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE triples SET valid_until = ? WHERE id = ? AND valid_until IS NULL",
                (end, tid),
            )
            return cur.rowcount > 0

    def timeline(self, entity: str | None = None) -> list[dict[str, Any]]:
        if entity:
            from lib.entity_aliases import canonicalize_entity

            entity = canonicalize_entity(entity, self._cfg)
        with self._conn() as conn:
            if entity:
                rows = conn.execute(
                    """
                    SELECT id, s, p, o, valid_from, valid_until, source FROM triples
                    WHERE s = ? OR o = ?
                    ORDER BY valid_from, id
                    """,
                    (entity, entity),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, s, p, o, valid_from, valid_until, source FROM triples
                    ORDER BY valid_from, id
                    """
                ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        with self._conn() as conn:
            total = conn.execute("SELECT count(*) FROM triples").fetchone()[0]
            active = conn.execute(
                "SELECT count(*) FROM triples WHERE valid_until IS NULL"
            ).fetchone()[0]
            n_ent = conn.execute("SELECT count(*) FROM entities").fetchone()[0]
            preds = [r[0] for r in conn.execute("SELECT DISTINCT p FROM triples").fetchall()]
        return {
            "backend": "sqlite",
            "entities": n_ent,
            "triples_total": total,
            "triples_active": active,
            "triples_expired": total - active,
            "predicates": sorted(preds),
            "kg_path": str(self._path),
        }

    def rebuild(self, vault: Path) -> dict[str, Any]:
        from lib.entity_aliases import canonicalize_entity

        wikilink_re = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
        added = 0
        today = _today()

        with self._conn() as conn:
            existing = {r[0] for r in conn.execute("SELECT id FROM triples").fetchall()}
            for rel, text in _walk_vault_md(vault):
                fm, body = _parse_frontmatter(text)
                tags = _tags_for_file(fm)
                page_name = canonicalize_entity(Path(rel).stem, self._cfg)

                for tag in tags:
                    tag_c = canonicalize_entity(str(tag), self._cfg)
                    tid = _triple_id(page_name, "tagged", tag_c)
                    if tid not in existing:
                        conn.execute(
                            """
                            INSERT INTO triples (id, s, p, o, valid_from, valid_until, source)
                            VALUES (?, ?, ?, ?, ?, NULL, ?)
                            """,
                            (tid, page_name, "tagged", tag_c, today, rel),
                        )
                        conn.execute(
                            "INSERT OR IGNORE INTO entities (name, first_seen) VALUES (?, ?)",
                            (page_name, today),
                        )
                        conn.execute(
                            "INSERT OR IGNORE INTO entities (name, first_seen) VALUES (?, ?)",
                            (tag_c, today),
                        )
                        existing.add(tid)
                        added += 1

                for m in wikilink_re.finditer(body):
                    target = canonicalize_entity(m.group(1).strip(), self._cfg)
                    if not target:
                        continue
                    tid = _triple_id(page_name, "links_to", target)
                    if tid not in existing:
                        conn.execute(
                            """
                            INSERT INTO triples (id, s, p, o, valid_from, valid_until, source)
                            VALUES (?, ?, ?, ?, ?, NULL, ?)
                            """,
                            (tid, page_name, "links_to", target, today, rel),
                        )
                        conn.execute(
                            "INSERT OR IGNORE INTO entities (name, first_seen) VALUES (?, ?)",
                            (page_name, today),
                        )
                        conn.execute(
                            "INSERT OR IGNORE INTO entities (name, first_seen) VALUES (?, ?)",
                            (target, today),
                        )
                        existing.add(tid)
                        added += 1

                kg_cfg = (self._cfg.get("knowledge_graph") or {}) if self._cfg else {}
                if kg_cfg.get("entity_detection", True):
                    from lib.entity_detector import extract_entities

                    for ent in extract_entities(body, cfg=self._cfg or {}):
                        ent_c = canonicalize_entity(ent, self._cfg)
                        if ent_c == page_name:
                            continue
                        tid = _triple_id(page_name, "mentions", ent_c)
                        if tid not in existing:
                            conn.execute(
                                """
                                INSERT INTO triples (id, s, p, o, valid_from, valid_until, source)
                                VALUES (?, ?, ?, ?, ?, NULL, ?)
                                """,
                                (tid, page_name, "mentions", ent_c, today, rel),
                            )
                            conn.execute(
                                "INSERT OR IGNORE INTO entities (name, first_seen) VALUES (?, ?)",
                                (page_name, today),
                            )
                            conn.execute(
                                "INSERT OR IGNORE INTO entities (name, first_seen) VALUES (?, ?)",
                                (ent_c, today),
                            )
                            existing.add(tid)
                            added += 1

            total = conn.execute("SELECT count(*) FROM triples").fetchone()[0]
            n_ent = conn.execute("SELECT count(*) FROM entities").fetchone()[0]
        return {"added": added, "total_triples": total, "entities": n_ent}

    def _all_triples(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, s, p, o, valid_from, valid_until, source FROM triples"
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            d["valid_until"] = d.get("valid_until")
            out.append(d)
        return out

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
