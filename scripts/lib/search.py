"""Pluggable vault search: FTS5 (default, stdlib) and grep (fallback)."""
from __future__ import annotations

import json
import logging
import re
import shutil
import sqlite3
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from lib.config_loader import DEFAULTS, resolve_storage_path
from lib.rank_fusion import reciprocal_rank_fusion

_log = logging.getLogger("llm_wiki.search")


@dataclass
class SearchResult:
    path: str
    title: str
    snippet: str
    score: float = 0.0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SearchBackend(Protocol):
    def search(
        self, query: str, *, limit: int = 5, tag: str | None = None, scope: str = "all"
    ) -> list[SearchResult]: ...

    def find_related(self, page_path: str, *, limit: int = 5) -> list[SearchResult]: ...

    def index_status(self) -> dict[str, Any]: ...

    def reindex(self) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip("'\"")
    body = text[m.end() :]
    return fm, body


def _title_from(fm: dict[str, str], body: str, path: str) -> str:
    if fm.get("title"):
        return fm["title"]
    heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    if heading:
        return heading.group(1).strip()
    return Path(path).stem


def _tags_for_file(fm: dict[str, str]) -> list[str]:
    raw = fm.get("llm_wiki_tags", "") or fm.get("tags", "")
    raw = raw.strip("[]")
    if not raw:
        return []
    return [t.strip().strip("'\"") for t in raw.split(",") if t.strip()]


_QUERY_STOPWORDS = frozenset(
    {
        "what",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "whose",
        "why",
        "how",
        "did",
        "does",
        "do",
        "are",
        "was",
        "were",
        "is",
        "am",
        "been",
        "being",
        "have",
        "has",
        "had",
        "the",
        "a",
        "an",
        "i",
        "my",
        "me",
        "we",
        "our",
        "us",
        "you",
        "your",
        "he",
        "she",
        "it",
        "its",
        "they",
        "them",
        "their",
        "this",
        "that",
        "these",
        "those",
        "there",
        "here",
        "then",
        "than",
        "with",
        "from",
        "into",
        "about",
        "after",
        "before",
        "during",
        "would",
        "could",
        "should",
        "will",
        "just",
        "also",
        "only",
        "both",
        "some",
        "any",
        "each",
        "every",
        "other",
        "such",
        "same",
        "very",
        "much",
        "too",
        "not",
        "no",
        "yes",
        "or",
        "and",
        "if",
        "as",
        "at",
        "be",
        "by",
        "on",
        "in",
        "of",
        "to",
        "so",
    }
)


def build_fts_and_query(question: str, *, max_terms: int = 4) -> str | None:
    """
    Build a strict AND query from the longest content-like terms (for fusion with
    a broad OR query). Returns None if there are not enough discriminative terms.
    """
    words: list[str] = []
    for w in re.findall(r"\w+", question, flags=re.UNICODE):
        lw = w.lower()
        if len(lw) <= 2 or lw in _QUERY_STOPWORDS:
            continue
        words.append(lw)
    seen: set[str] = set()
    uniq: list[str] = []
    for w in words:
        if w not in seen:
            seen.add(w)
            uniq.append(w)
    uniq.sort(key=len, reverse=True)
    picked = uniq[:max_terms]
    if len(picked) < 2:
        return None
    return " AND ".join(picked)


def prepare_fts5_match_query(raw: str) -> str:
    """
    Build a safe FTS5 MATCH string. Raw user questions often contain punctuation
    (`?`, quotes, etc.) that triggers fts5 syntax errors and yields zero results.
    We tokenize into word/alnum runs and OR them so BM25 can still rank.
    """
    s = re.sub(r"[^\w\u0080-\uFFFF]+", " ", raw, flags=re.UNICODE)
    words = [w for w in s.split() if len(w) > 1][:48]
    if not words:
        return "x"
    if len(words) == 1:
        return words[0]
    return " OR ".join(words)


def _walk_vault_md(vault: Path) -> list[tuple[str, str]]:
    """Return (relative_path, full_text) for every .md in wiki/ and raw/."""
    files: list[tuple[str, str]] = []
    for subdir in ("wiki", "raw"):
        d = vault / subdir
        if not d.is_dir():
            continue
        for md in sorted(d.rglob("*.md")):
            if ".og" in md.parts:
                continue
            try:
                text = md.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = md.relative_to(vault).as_posix()
            files.append((rel, text))
    return files


# ---------------------------------------------------------------------------
# FTS5 backend (default) — BM25 ranked full-text search via stdlib sqlite3
# ---------------------------------------------------------------------------

_FTS5_DB_NAME = ".search.sqlite3"

_SQLITE_PERF_DEFAULTS = DEFAULTS["performance"]["sqlite"]

# SQLite journal_mode / synchronous — only allow known-safe tokens (config may be user-edited).
_ALLOWED_JOURNAL_MODES = frozenset({"wal", "delete", "truncate", "persist", "memory", "off"})
_ALLOWED_SYNCHRONOUS_STR = frozenset({"off", "normal", "full", "extra", "0", "1", "2", "3"})
_INT32_MIN = -(2**31)
_INT32_MAX = 2**31 - 1


def _sanitize_journal_mode(value: Any) -> str:
    s = str(value).lower().strip()
    if s in _ALLOWED_JOURNAL_MODES and re.fullmatch(r"[a-z]+", s):
        return s
    return str(_SQLITE_PERF_DEFAULTS["journal_mode"])


def _sanitize_synchronous(value: Any) -> str | int:
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 3:
        return value
    s = str(value).lower().strip()
    if s in _ALLOWED_SYNCHRONOUS_STR:
        if s in {"0", "1", "2", "3"}:
            return int(s)
        if re.fullmatch(r"[a-z]+", s):
            return s
    d = _SQLITE_PERF_DEFAULTS["synchronous"]
    return d if isinstance(d, int) and not isinstance(d, bool) else str(d)


def _sanitize_int_pragma(
    value: Any,
    default: int,
    *,
    min_v: int,
    max_v: int,
) -> int:
    try:
        i = int(value)
    except (TypeError, ValueError):
        return default
    if not min_v <= i <= max_v:
        return default
    return i


class FTS5SearchBackend:
    def __init__(self, vault: Path, cfg: dict[str, Any] | None = None):
        self._vault = vault
        self._cfg = cfg or {}
        self._db_path = resolve_storage_path(vault, self._cfg, "search_db")
        perf = (self._cfg.get("performance") or {}).get("sqlite") or {}
        self._journal_mode = _sanitize_journal_mode(
            perf.get("journal_mode", _SQLITE_PERF_DEFAULTS["journal_mode"])
        )
        self._synchronous = _sanitize_synchronous(
            perf.get("synchronous", _SQLITE_PERF_DEFAULTS["synchronous"])
        )
        self._cache_size = _sanitize_int_pragma(
            perf.get("cache_size", _SQLITE_PERF_DEFAULTS["cache_size"]),
            int(_SQLITE_PERF_DEFAULTS["cache_size"]),
            min_v=_INT32_MIN,
            max_v=_INT32_MAX,
        )
        # SQLite allows large mmap values; cap to avoid absurd config.
        self._mmap_size = _sanitize_int_pragma(
            perf.get("mmap_size", _SQLITE_PERF_DEFAULTS["mmap_size"]),
            int(_SQLITE_PERF_DEFAULTS["mmap_size"]),
            min_v=0,
            max_v=2**40,
        )
        self._busy_timeout = _sanitize_int_pragma(
            perf.get("busy_timeout", _SQLITE_PERF_DEFAULTS["busy_timeout"]),
            int(_SQLITE_PERF_DEFAULTS["busy_timeout"]),
            min_v=0,
            max_v=_INT32_MAX,
        )
        self._metrics: Any = None
        self._ensure_table()

    def _conn(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA journal_mode={self._journal_mode}")
        sync = self._synchronous
        conn.execute(f"PRAGMA synchronous={sync}")
        conn.execute(f"PRAGMA cache_size={self._cache_size}")
        conn.execute(f"PRAGMA mmap_size={self._mmap_size}")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute(f"PRAGMA busy_timeout={self._busy_timeout}")
        return conn

    def _ensure_table(self) -> None:
        with self._conn() as conn:
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS pages USING fts5("
                "  path, title, body, tags,"
                "  tokenize='porter unicode61'"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS meta ("
                "  key TEXT PRIMARY KEY, value TEXT"
                ")"
            )

    def reindex(self) -> dict[str, Any]:
        t0 = time.monotonic()
        files = _walk_vault_md(self._vault)
        rows = []
        for rel, text in files:
            fm, body = _parse_frontmatter(text)
            title = _title_from(fm, body, rel)
            tags = ", ".join(_tags_for_file(fm))
            rows.append((rel, title, body[:50000], tags))
        with self._conn() as conn:
            conn.execute("DELETE FROM pages")
            conn.executemany(
                "INSERT INTO pages (path, title, body, tags) VALUES (?, ?, ?, ?)",
                rows,
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('file_count', ?)",
                (str(len(files)),),
            )
            import datetime
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_indexed', ?)",
                (datetime.datetime.now().isoformat(),),
            )
        elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
        if self._metrics:
            self._metrics.record("search.reindex_ms", elapsed_ms, meta={"files": len(files)})
        return {"indexed": len(files), "db": str(self._db_path), "elapsed_ms": elapsed_ms}

    def _auto_index_if_empty(self) -> None:
        with self._conn() as conn:
            row = conn.execute("SELECT count(*) FROM pages").fetchone()
            if row[0] == 0:
                self.reindex()

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        tag: str | None = None,
        scope: str = "all",
        sanitize_query: bool = True,
    ) -> list[SearchResult]:
        t0 = time.monotonic()
        self._auto_index_if_empty()
        safe = prepare_fts5_match_query(query) if sanitize_query else query.strip()
        fts_query = safe
        if tag:
            safe_tag = tag.replace('"', '""')
            fts_query = f'tags:"{safe_tag}" AND ({safe})'
        if scope == "wiki":
            fts_query = f'path:"wiki/" AND ({fts_query})'
        elif scope == "raw":
            fts_query = f'path:"raw/" AND ({fts_query})'
        elif scope == "memory":
            fts_query = f'path:"raw/memory/" AND ({fts_query})'

        sql = (
            "SELECT path, title, snippet(pages, 2, '»', '«', '…', 40) AS snip,"
            "       bm25(pages, 1.0, 5.0, 1.0, 2.0) AS score,"
            "       tags"
            "  FROM pages WHERE pages MATCH ?"
            "  ORDER BY score"
            "  LIMIT ?"
        )
        results: list[SearchResult] = []
        try:
            with self._conn() as conn:
                for row in conn.execute(sql, (fts_query, limit)):
                    results.append(
                        SearchResult(
                            path=row["path"],
                            title=row["title"],
                            snippet=row["snip"] or "",
                            score=round(-row["score"], 4),
                            tags=[t.strip() for t in (row["tags"] or "").split(",") if t.strip()],
                        )
                    )
        except sqlite3.OperationalError as exc:
            _log.warning("FTS5 search failed: %s (query=%r)", exc, query[:100])
        if self._metrics:
            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
            self._metrics.record(
                "search.query_ms", elapsed_ms,
                meta={"query": query[:100], "results": len(results), "scope": scope},
            )
        return results

    def find_related(self, page_path: str, *, limit: int = 5) -> list[SearchResult]:
        self._auto_index_if_empty()
        with self._conn() as conn:
            row = conn.execute("SELECT title, tags FROM pages WHERE path = ?", (page_path,)).fetchone()
            if not row:
                return []
            terms = (row["title"] or "") + " " + (row["tags"] or "")
        terms = re.sub(r"[^\w\s]", " ", terms)
        words = [w for w in terms.split() if len(w) > 2][:10]
        if not words:
            return []
        fts_query = " OR ".join(words)
        return [r for r in self.search(fts_query, limit=limit + 1) if r.path != page_path][:limit]

    def index_status(self) -> dict[str, Any]:
        info: dict[str, Any] = {"backend": "fts5", "db_path": str(self._db_path)}
        try:
            with self._conn() as conn:
                row = conn.execute("SELECT count(*) FROM pages").fetchone()
                info["indexed_pages"] = row[0]
                for r in conn.execute("SELECT key, value FROM meta"):
                    info[r["key"]] = r["value"]
        except Exception:
            info["indexed_pages"] = 0
        return info


# ---------------------------------------------------------------------------
# Grep backend (fallback) — ripgrep or stdlib re
# ---------------------------------------------------------------------------

class GrepSearchBackend:
    def __init__(self, vault: Path):
        self._vault = vault
        self._has_rg = shutil.which("rg") is not None

    def search(
        self, query: str, *, limit: int = 5, tag: str | None = None, scope: str = "all"
    ) -> list[SearchResult]:
        if self._has_rg:
            return self._search_rg(query, limit=limit, tag=tag, scope=scope)
        return self._search_re(query, limit=limit, tag=tag, scope=scope)

    def _search_rg(
        self, query: str, *, limit: int = 5, tag: str | None = None, scope: str = "all"
    ) -> list[SearchResult]:
        dirs = self._scope_dirs(scope)
        if not dirs:
            return []
        cmd = [
            "rg",
            "--json",
            "-i",
            "--fixed-strings",
            "-m",
            "3",
            "--max-count",
            str(limit * 3),
            query,
        ]
        cmd.extend(str(d) for d in dirs)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return self._search_re(query, limit=limit, tag=tag, scope=scope)

        results: list[SearchResult] = []
        seen: set[str] = set()
        for line in proc.stdout.splitlines():
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") != "match":
                continue
            data = obj["data"]
            abs_path = data["path"]["text"]
            try:
                rel = str(Path(abs_path).relative_to(self._vault))
            except ValueError:
                rel = abs_path
            if rel in seen:
                continue
            seen.add(rel)
            snippet = data["lines"]["text"].strip()[:200]
            try:
                text = Path(abs_path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            fm, body = _parse_frontmatter(text)
            tags = _tags_for_file(fm)
            if tag and tag not in tags:
                continue
            results.append(
                SearchResult(
                    path=rel,
                    title=_title_from(fm, body, rel),
                    snippet=snippet,
                    score=1.0,
                    tags=tags,
                )
            )
            if len(results) >= limit:
                break
        return results

    def _search_re(
        self, query: str, *, limit: int = 5, tag: str | None = None, scope: str = "all"
    ) -> list[SearchResult]:
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            pattern = re.compile(re.escape(query), re.IGNORECASE)

        results: list[SearchResult] = []
        for rel, text in _walk_vault_md(self._vault):
            if scope == "wiki" and not rel.startswith("wiki/"):
                continue
            if scope == "raw" and not rel.startswith("raw/"):
                continue
            if scope == "memory" and not rel.startswith("raw/memory/"):
                continue
            fm, body = _parse_frontmatter(text)
            m = pattern.search(body)
            if not m:
                continue
            tags = _tags_for_file(fm)
            if tag and tag not in tags:
                continue
            start = max(0, m.start() - 40)
            snippet = body[start : m.end() + 80].replace("\n", " ").strip()
            results.append(
                SearchResult(
                    path=rel,
                    title=_title_from(fm, body, rel),
                    snippet=snippet,
                    score=1.0,
                    tags=tags,
                )
            )
            if len(results) >= limit:
                break
        return results

    def _scope_dirs(self, scope: str) -> list[Path]:
        if scope == "wiki":
            d = self._vault / "wiki"
            return [d] if d.is_dir() else []
        if scope == "raw":
            d = self._vault / "raw"
            return [d] if d.is_dir() else []
        if scope == "memory":
            d = self._vault / "raw" / "memory"
            return [d] if d.is_dir() else []
        return [d for d in [self._vault / "wiki", self._vault / "raw"] if d.is_dir()]

    def find_related(self, page_path: str, *, limit: int = 5) -> list[SearchResult]:
        full = self._vault / page_path
        if not full.is_file():
            return []
        text = full.read_text(encoding="utf-8", errors="replace")
        fm, body = _parse_frontmatter(text)
        title = _title_from(fm, body, page_path)
        words = re.findall(r"\b[a-zA-Z]{4,}\b", title)[:5]
        if not words:
            return []
        query = "|".join(words)
        return [r for r in self.search(query, limit=limit + 1) if r.path != page_path][:limit]

    def index_status(self) -> dict[str, Any]:
        return {"backend": "grep", "note": "grep backend has no persistent index"}

    def reindex(self) -> dict[str, Any]:
        return {"backend": "grep", "note": "grep backend has no index to rebuild"}


# ---------------------------------------------------------------------------
# Hybrid (FTS5 + ChromaDB RRF)
# ---------------------------------------------------------------------------


class HybridSearchBackend:
    """BM25 + semantic similarity via reciprocal rank fusion."""

    def __init__(self, vault: Path, cfg: dict[str, Any], chroma: Any) -> None:
        self._vault = vault
        self._cfg = cfg
        self._fts = FTS5SearchBackend(vault, cfg)
        self._chroma = chroma
        mcp = cfg.get("mcp") or {}
        self._rrf_k = int(mcp.get("hybrid_rrf_k", 60))
        self._metrics: Any = None

    def __setattr__(self, name: str, value: Any) -> None:
        object.__setattr__(self, name, value)
        if name == "_metrics":
            if getattr(self, "_fts", None) is not None:
                self._fts._metrics = value  # type: ignore[attr-defined]
            if getattr(self, "_chroma", None) is not None:
                self._chroma._metrics = value  # type: ignore[attr-defined]

    @staticmethod
    def _merge_rrf_results(
        fused_paths: list[str],
        fts_results: list[SearchResult],
        chroma_results: list[SearchResult],
    ) -> list[SearchResult]:
        fts_map = {r.path: r for r in fts_results}
        chroma_map = {r.path: r for r in chroma_results}
        out: list[SearchResult] = []
        for path in fused_paths:
            fts_r = fts_map.get(path)
            chroma_r = chroma_map.get(path)
            if fts_r and chroma_r:
                out.append(
                    SearchResult(
                        path=path,
                        title=fts_r.title or chroma_r.title,
                        snippet=fts_r.snippet,
                        score=max(fts_r.score, chroma_r.score),
                        tags=fts_r.tags if fts_r.tags else chroma_r.tags,
                    )
                )
            elif fts_r:
                out.append(fts_r)
            elif chroma_r:
                out.append(chroma_r)
        return out

    def search(
        self, query: str, *, limit: int = 5, tag: str | None = None, scope: str = "all"
    ) -> list[SearchResult]:
        n = max(limit * 4, 20)
        fts_results = self._fts.search(query, limit=n, tag=tag, scope=scope)
        chroma_results = self._chroma.search(query, limit=n, tag=tag, scope=scope)
        paths_a = [r.path for r in fts_results]
        paths_b = [r.path for r in chroma_results]
        fused = reciprocal_rank_fusion([paths_a, paths_b], k=self._rrf_k)
        merged = self._merge_rrf_results(fused, fts_results, chroma_results)
        return merged[:limit]

    def find_related(self, page_path: str, *, limit: int = 5) -> list[SearchResult]:
        return self._chroma.find_related(page_path, limit=limit)

    def index_status(self) -> dict[str, Any]:
        return {
            "backend": "hybrid",
            "chromadb_available": True,
            "fts": self._fts.index_status(),
            "chromadb": self._chroma.index_status(),
        }

    def reindex(self) -> dict[str, Any]:
        fts_r = self._fts.reindex()
        chroma_r = self._chroma.reindex()
        return {"backend": "hybrid", "fts": fts_r, "chromadb": chroma_r}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_search_backend(vault: Path, cfg: dict[str, Any]) -> SearchBackend:
    import logging

    log = logging.getLogger("llm_wiki.search")
    backend_name = (cfg.get("mcp") or {}).get("search_backend", "fts5")
    if backend_name == "chromadb":
        try:
            from lib.search_chromadb import ChromaDBSearchBackend

            return ChromaDBSearchBackend(vault, cfg)
        except ImportError:
            log.warning(
                "chromadb not installed; falling back to grep search. Install: pip install chromadb"
            )
            return GrepSearchBackend(vault)
        except Exception as e:
            log.warning("ChromaDB init failed (%s); falling back to grep.", e)
            return GrepSearchBackend(vault)
    if backend_name == "hybrid":
        try:
            from lib.search_chromadb import ChromaDBSearchBackend

            chroma = ChromaDBSearchBackend(vault, cfg)
            return HybridSearchBackend(vault, cfg, chroma)
        except ImportError:
            log.warning(
                "chromadb not installed; hybrid search requires chromadb. Falling back to fts5. Install: pip install chromadb"
            )
            return FTS5SearchBackend(vault, cfg)
        except Exception as e:
            log.warning("ChromaDB init failed (%s); hybrid falling back to fts5.", e)
            return FTS5SearchBackend(vault, cfg)
    if backend_name == "fts5":
        return FTS5SearchBackend(vault, cfg)
    return GrepSearchBackend(vault)
