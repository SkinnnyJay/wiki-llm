"""ChromaDB semantic search backend (optional dependency: pip install chromadb)."""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from lib.config_loader import resolve_storage_path
from lib.search import (
    SearchResult,
    _parse_frontmatter,
    _tags_for_file,
    _title_from,
    _walk_vault_md,
    _wing_room_for_file,
)

DEFAULT_COLLECTION_NAME = "wiki_pages"
DEFAULT_BATCH_SIZE = 100
MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 10_000
DEFAULT_DISTANCE_FUNCTION = "cosine"
ALLOWED_DISTANCE_FUNCTIONS = frozenset({"cosine", "l2", "ip"})
MAX_INDEX_DOCUMENT_CHARS = 80_000
MAX_QUERY_DOCUMENT_CHARS = 8_000
MAX_SNIPPET_CHARS = 200


def _mapping_or_empty(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _positive_batch_size(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return DEFAULT_BATCH_SIZE
    try:
        batch_size = int(value)
    except (TypeError, ValueError):
        return DEFAULT_BATCH_SIZE
    if not MIN_BATCH_SIZE <= batch_size <= MAX_BATCH_SIZE:
        return DEFAULT_BATCH_SIZE
    return batch_size


def _distance_function(value: object) -> str:
    candidate = str(value).strip().lower()
    return candidate if candidate in ALLOWED_DISTANCE_FUNCTIONS else DEFAULT_DISTANCE_FUNCTION


class ChromaDBSearchBackend:
    """Embed wiki+raw markdown in a local ChromaDB collection."""

    def __init__(self, vault: Path, cfg: dict[str, Any]):
        import chromadb

        self._vault = vault
        self._cfg = cfg
        self._metrics: Any = None
        performance = _mapping_or_empty(cfg.get("performance"))
        perf = _mapping_or_empty(performance.get("chromadb"))
        self._collection_name = str(perf.get("collection_name") or DEFAULT_COLLECTION_NAME)
        self._batch_size = _positive_batch_size(perf.get("batch_size", DEFAULT_BATCH_SIZE))
        self._distance_function = _distance_function(perf.get("distance_fn"))
        chroma_dir = resolve_storage_path(vault, cfg, "chromadb_dir")
        chroma_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(chroma_dir))
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": self._distance_function},
        )

    def reindex(self) -> dict[str, Any]:
        t0 = time.monotonic()
        files = _walk_vault_md(self._vault)
        try:
            self._client.delete_collection(self._collection_name)
        except Exception:
            pass
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": self._distance_function},
        )
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for rel, text in files:
            fm, body = _parse_frontmatter(text)
            title = _title_from(fm, body, rel)
            tags = _tags_for_file(fm)
            wn, rm = _wing_room_for_file(fm)
            chunk = (title + "\n\n" + body)[:MAX_INDEX_DOCUMENT_CHARS]
            ids.append(rel)
            documents.append(chunk)
            metadatas.append(
                {
                    "path": rel,
                    "title": title,
                    "tags": ",".join(tags),
                    "wing": wn,
                    "room": rm,
                }
            )
        for i in range(0, len(ids), self._batch_size):
            self._collection.add(
                ids=ids[i : i + self._batch_size],
                documents=documents[i : i + self._batch_size],
                metadatas=metadatas[i : i + self._batch_size],
            )
        elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
        if self._metrics:
            self._metrics.record("search.reindex_ms", elapsed_ms, meta={"files": len(files), "backend": "chromadb"})
        return {
            "indexed": len(files),
            "backend": "chromadb",
            "collection": self._collection_name,
            "elapsed_ms": elapsed_ms,
        }

    def _maybe_reindex_if_empty(self) -> None:
        try:
            if self._collection.count() == 0:
                self.reindex()
        except Exception:
            self.reindex()

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        tag: str | None = None,
        scope: str = "all",
        wing: str | None = None,
        room: str | None = None,
    ) -> list[SearchResult]:
        t0 = time.monotonic()
        self._maybe_reindex_if_empty()
        n_results = min(max(limit * 4, limit), 50)
        res = self._collection.query(query_texts=[query], n_results=n_results)
        ids = res.get("ids") or [[]]
        docs = res.get("documents") or [[]]
        dists = res.get("distances") or [[]]
        metas = res.get("metadatas") or [[]]
        out: list[SearchResult] = []
        row_ids = ids[0] if ids else []
        row_docs = docs[0] if docs else []
        row_dists = dists[0] if dists else []
        row_metas = metas[0] if metas else []
        for i, doc_id in enumerate(row_ids):
            meta = row_metas[i] if i < len(row_metas) else {}
            path = str(meta.get("path") or doc_id)
            if scope == "wiki" and not path.startswith("wiki/"):
                continue
            if scope == "raw" and not path.startswith("raw/"):
                continue
            if scope == "memory" and "raw/memory/" not in path:
                continue
            tags_s = str(meta.get("tags") or "")
            tag_list = [t.strip() for t in tags_s.split(",") if t.strip()]
            if tag and tag not in tag_list:
                continue
            wmeta = str(meta.get("wing") or "")
            rmeta = str(meta.get("room") or "")
            if wing and wmeta != wing:
                continue
            if room and rmeta != room:
                continue
            title = str(meta.get("title") or Path(path).stem)
            body_snip = (row_docs[i] if i < len(row_docs) else "") or ""
            body_snip = body_snip.replace("\n", " ")[:MAX_SNIPPET_CHARS]
            dist = row_dists[i] if i < len(row_dists) else None
            score = round(1.0 - float(dist), 4) if dist is not None else 0.5
            out.append(
                SearchResult(
                    path=path,
                    title=title,
                    snippet=body_snip + ("…" if len(body_snip) >= MAX_SNIPPET_CHARS else ""),
                    score=score,
                    tags=tag_list,
                    wing=wmeta,
                    room=rmeta,
                )
            )
            if len(out) >= limit:
                break
        if self._metrics:
            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
            self._metrics.record(
                "search.query_ms",
                elapsed_ms,
                meta={"query": query[:100], "results": len(out), "scope": scope},
            )
        return out

    def find_related(self, page_path: str, *, limit: int = 5) -> list[SearchResult]:
        self._maybe_reindex_if_empty()
        try:
            got = self._collection.get(ids=[page_path], include=["documents", "metadatas"])
            if not got.get("ids"):
                return []
            doc = (got.get("documents") or [None])[0]
            if not doc:
                return []
        except Exception:
            return []
        res = self._collection.query(
            query_texts=[doc[:MAX_QUERY_DOCUMENT_CHARS]], n_results=limit + 3
        )
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        out: list[SearchResult] = []
        for i, pid in enumerate(ids):
            if pid == page_path:
                continue
            meta = metas[i] if i < len(metas) else {}
            path = str(meta.get("path") or pid)
            title = str(meta.get("title") or Path(path).stem)
            tags_s = str(meta.get("tags") or "")
            tag_list = [t.strip() for t in tags_s.split(",") if t.strip()]
            body_snip = (docs[i] if i < len(docs) else "") or ""
            body_snip = re.sub(r"\s+", " ", body_snip)[:MAX_SNIPPET_CHARS]
            dist = dists[i] if i < len(dists) else None
            score = round(1.0 - float(dist), 4) if dist is not None else 0.5
            wmeta = str(meta.get("wing") or "")
            rmeta = str(meta.get("room") or "")
            out.append(
                SearchResult(
                    path=path,
                    title=title,
                    snippet=body_snip,
                    score=score,
                    tags=tag_list,
                    wing=wmeta,
                    room=rmeta,
                )
            )
            if len(out) >= limit:
                break
        return out

    def index_status(self) -> dict[str, Any]:
        try:
            n = self._collection.count()
        except Exception:
            n = 0
        return {
            "backend": "chromadb",
            "indexed_pages": n,
            "collection": self._collection_name,
        }
