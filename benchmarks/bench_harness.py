"""Shared benchmark harness: scoring, hybrid fusion, vault layout, metrics."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
from datetime import datetime, timezone
from collections import Counter
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

# Repo scripts on path when run as python -m or from llm_wiki
import sys

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lib.compressors import Compressor, RawCompressor, get_compressor
from lib.config_loader import DEFAULTS, deep_merge, load_config, resolve_storage_path, save_config
from lib.metrics import MetricsRecorder
from lib.rank_fusion import reciprocal_rank_fusion


def dcg(relevances: list[float], k: int) -> float:
    score = 0.0
    for i, rel in enumerate(relevances[:k]):
        score += rel / math.log2(i + 2)
    return score


def ndcg_at_k(
    rankings: list[int],
    correct_indices: set[int],
    k: int,
) -> float:
    """rankings: corpus indices ordered best-first. correct_indices: gold doc indices."""
    relevances = [1.0 if idx in correct_indices else 0.0 for idx in rankings[:k]]
    ideal = sorted(relevances, reverse=True)
    idcg = dcg(ideal, k)
    if idcg == 0:
        return 0.0
    return dcg(relevances, k) / idcg


def recall_at_k(rankings: list[int], correct_indices: set[int], k: int) -> float:
    top = set(rankings[:k])
    return 1.0 if correct_indices & top else 0.0


def reciprocal_rank_fusion_weighted(
    weighted_lists: list[tuple[list[str], float]],
    *,
    k: int = 60,
) -> list[str]:
    """RRF with per-list weights (e.g. down-weight haystack TF-IDF vs BM25 OR)."""
    scores: dict[str, float] = {}
    for rlist, w in weighted_lists:
        if w <= 0:
            continue
        for rank, path in enumerate(rlist):
            scores[path] = scores.get(path, 0.0) + w * (1.0 / (k + rank + 1))
    return sorted(scores.keys(), key=lambda p: -scores[p])


def _sanitize_id(sess_id: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", str(sess_id))[:200]


def session_markdown_body(
    session: list[dict[str, Any]],
    *,
    include_assistant: bool = True,
) -> str:
    """Format LongMemEval session turns as markdown."""
    lines: list[str] = []
    for turn in session:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role == "assistant" and not include_assistant:
            continue
        prefix = "User" if role == "user" else "Assistant"
        lines.append(f"**{prefix}:** {content}")
    return "\n\n".join(lines)


def write_benchmark_vault(
    vault: Path,
    cfg: dict[str, Any],
    *,
    sessions: list[list[dict[str, Any]]],
    session_ids: list[str],
    dates: list[str],
    compressor: Compressor,
    subdir: str = "raw/bench",
) -> dict[str, str]:
    """
    Write one markdown file per session. Returns mapping path -> session_id.
    """
    (vault / subdir).mkdir(parents=True, exist_ok=True)
    path_to_sid: dict[str, str] = {}
    for session, sid, date in zip(sessions, session_ids, dates):
        body = session_markdown_body(session, include_assistant=True)
        compressed = compressor.compress(body, metadata={"session_id": sid, "date": date})
        safe = _sanitize_id(sid)
        rel = f"{subdir}/{safe}.md"
        full = vault / rel
        fm = "\n".join(
            [
                "---",
                f'title: "Session {safe}"',
                f"session_id: {json.dumps(sid)}",
                f"bench_date: {json.dumps(date)}",
                "---",
                "",
            ]
        )
        full.write_text(fm + compressed, encoding="utf-8")
        path_to_sid[rel.replace("\\", "/")] = sid
    return path_to_sid


def build_benchmark_config(base_cfg: dict[str, Any], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = deep_merge(deep_merge(DEFAULTS, base_cfg), overrides or {})
    cfg.setdefault("benchmark", deep_merge(DEFAULTS.get("benchmark", {}), cfg.get("benchmark") or {}))
    return cfg


def get_benchmark_search_fn(
    vault: Path,
    cfg: dict[str, Any],
    *,
    backend_name: str | None = None,
) -> Callable[[str, int], list[str]]:
    """
    Return callable (query, limit) -> list of vault-relative paths, best first.
    """
    from lib.search import FTS5SearchBackend, GrepSearchBackend, get_search_backend

    bcfg = (cfg.get("benchmark") or {}).get("search") or {}
    name = backend_name or bcfg.get("backend", "fts5")
    hybrid = bool(bcfg.get("hybrid_enabled")) and name == "hybrid"

    if hybrid:
        fts = FTS5SearchBackend(vault, cfg)
        try:
            from lib.search_chromadb import ChromaDBSearchBackend

            chroma = ChromaDBSearchBackend(vault, cfg)
        except Exception:
            chroma = None

        def _hybrid(q: str, limit: int) -> list[str]:
            n = max(limit * 4, 20)
            rrf_k = int(bcfg.get("hybrid_k", 60))
            paths_a = [r.path for r in fts.search(q, limit=n)]
            paths_b = [r.path for r in chroma.search(q, limit=n)] if chroma else []
            if not paths_b:
                return paths_a[:limit]
            fused = reciprocal_rank_fusion([paths_a, paths_b], k=rrf_k)
            return fused[:limit]

        return _hybrid

    if name == "grep":
        be = GrepSearchBackend(vault)
    elif name == "chromadb":
        cfg_m = deep_merge(cfg, {"mcp": {"search_backend": "chromadb"}})
        be = get_search_backend(vault, cfg_m)
    else:
        be = get_search_backend(vault, cfg)

    def _one(q: str, limit: int) -> list[str]:
        return [r.path for r in be.search(q, limit=limit)]

    return _one


def dual_fts_retrieve_paths(
    vault: Path,
    cfg: dict[str, Any],
    question: str,
    *,
    limit: int,
    rrf_k: int = 60,
) -> list[str]:
    """
    Reciprocal rank fusion of a broad OR query (BM25) and a tight AND query
    built from long content terms — improves ranking without ChromaDB.
    """
    from lib.search import FTS5SearchBackend, build_fts_and_query

    fts = FTS5SearchBackend(vault, cfg)
    paths_or = [r.path for r in fts.search(question, limit=limit)]
    q_and = build_fts_and_query(question)
    if not q_and:
        return paths_or
    try:
        paths_and = [r.path for r in fts.search(q_and, limit=limit, sanitize_query=False)]
    except Exception:
        paths_and = []
    if not paths_and:
        return paths_or
    return reciprocal_rank_fusion([paths_or, paths_and], k=rrf_k)


_PRF_SKIP = frozenset(
    {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "to", "of", "in", "for", "on", "with",
        "at", "by", "from", "as", "into", "about", "between", "through", "during",
        "before", "after", "above", "below", "up", "down", "out", "off", "over",
        "under", "again", "further", "then", "once", "here", "there", "when",
        "where", "why", "how", "all", "each", "every", "both", "few", "more",
        "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same",
        "so", "than", "too", "very", "just", "don", "now", "and", "but", "or",
        "if", "while", "that", "this", "these", "those", "it", "its", "i", "we",
        "you", "he", "she", "they", "me", "him", "her", "us", "them", "my", "your",
        "his", "our", "their", "what", "which", "who", "whom", "also", "much",
        "many", "like", "because", "since", "get", "got", "use", "used", "using",
        "make", "made", "thing", "things", "way", "well", "really", "want", "need",
    }
)


def _bench_doc_tokens(
    vault: Path,
    rel: str,
    max_chars: int,
    *,
    head_tail: bool = True,
) -> list[str]:
    """
    Tokenize benchmark markdown bodies for TF-IDF / PRF. When ``head_tail`` is True
    and the body exceeds ``max_chars``, take tokens from the start *and* end so
    answers buried late in long chats still contribute (same idea as LLM excerpts).
    """
    p = vault / rel
    try:
        full = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    if full.startswith("---"):
        end = full.find("\n---\n", 3)
        if end != -1:
            body = full[end + 5 :]
        else:
            body = full
    else:
        body = full
    if len(body) <= max_chars or not head_tail:
        chunk = body[:max_chars]
    else:
        half = max(max_chars // 2 - 40, 400)
        chunk = body[:half] + "\n" + body[-half:]
    return [w.lower() for w in re.findall(r"\w+", chunk, flags=re.UNICODE) if len(w) > 2]


def tfidf_corpus_rank_from_tokens(
    question: str,
    docs_tokens: dict[str, list[str]],
) -> list[str]:
    """TF×IDF ranking given pre-tokenized haystack bodies (one pass per question)."""
    all_paths = list(docs_tokens.keys())
    if not all_paths:
        return []
    df: dict[str, int] = {}
    for toks in docs_tokens.values():
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    n_docs = len(all_paths)
    q_words = [w.lower() for w in re.findall(r"\w+", question, flags=re.UNICODE) if len(w) > 2]
    if not q_words:
        return all_paths
    q_freq = Counter(q_words)
    bigrams: list[str] = []
    for i in range(len(q_words) - 1):
        bigrams.append(f"{q_words[i]} {q_words[i + 1]}")
    scores: dict[str, float] = {}
    for rel, toks in docs_tokens.items():
        tf = Counter(toks)
        s = 0.0
        for term, qw in q_freq.items():
            c = tf.get(term, 0)
            if c == 0:
                continue
            idf = math.log((n_docs + 1) / (df.get(term, 0) + 1)) + 1.0
            tf_w = 1.0 + math.log(c)
            s += tf_w * idf * (1.0 + 0.15 * qw)
        low = " ".join(toks)
        for bg in bigrams:
            if bg in low:
                s += 0.85
        scores[rel] = s
    return sorted(all_paths, key=lambda p: -scores.get(p, 0.0))


def tfidf_corpus_rank_paths(
    question: str,
    path_to_sid: dict[str, str],
    vault: Path,
    *,
    max_chars: int = 80000,
) -> list[str]:
    """
    Rank haystack sessions by TF×IDF using the question terms (haystack = corpus).
    """
    all_paths = list(path_to_sid.keys())
    if not all_paths:
        return []
    docs_tokens = {rel: _bench_doc_tokens(vault, rel, max_chars) for rel in all_paths}
    return tfidf_corpus_rank_from_tokens(question, docs_tokens)


def prf_or_rrf_paths(
    vault: Path,
    cfg: dict[str, Any],
    question: str,
    *,
    limit: int,
    rrf_k: int = 60,
    path_to_sid: dict[str, str] | None = None,
    tfidf_rrf: bool = True,
    docs_tokens: dict[str, list[str]] | None = None,
    rrf_boost_or: int = 2,
    tfidf_rrf_weight: float = 1.0,
) -> list[str]:
    """
    LME retrieval: RRF of (1) broad OR BM25 (optionally duplicated to weight FTS),
    (2) PRF-augmented query from the top-1 hit, (3) optional haystack TF×IDF.
    Pass ``docs_tokens`` to tokenize each file once per question (faster).
    ``tfidf_rrf_weight`` scales the TF×IDF list (use <1 when BM25 already ranks well).
    """
    from lib.search import FTS5SearchBackend

    fts = FTS5SearchBackend(vault, cfg)
    paths_or = [r.path for r in fts.search(question, limit=limit)]
    boost = max(1, min(int(rrf_boost_or), 4))
    weighted: list[tuple[list[str], float]] = [(paths_or, 1.0)] * boost

    top = fts.search(question, limit=1)
    if top:
        rel0 = top[0].path
        if docs_tokens is not None and rel0 in docs_tokens:
            words = [w for w in docs_tokens[rel0] if w not in _PRF_SKIP]
        else:
            p = vault / rel0
            try:
                raw = p.read_text(encoding="utf-8", errors="replace")[:40000]
            except OSError:
                raw = ""
            if raw.startswith("---"):
                end = raw.find("\n---\n", 3)
                if end != -1:
                    raw = raw[end + 5 :]
            words = [w.lower() for w in re.findall(r"\w+", raw) if len(w) > 2]
            words = [w for w in words if w not in _PRF_SKIP]
        freq = Counter(words)
        extra = [w for w, _ in freq.most_common(16)]
        if extra:
            aug = question + " " + " ".join(extra)
            paths_aug = [r.path for r in fts.search(aug, limit=limit)]
            if paths_aug:
                weighted.append((paths_aug, 1.0))

    if tfidf_rrf and path_to_sid and tfidf_rrf_weight > 0:
        if docs_tokens is not None:
            paths_tfidf = tfidf_corpus_rank_from_tokens(question, docs_tokens)
        else:
            paths_tfidf = tfidf_corpus_rank_paths(question, path_to_sid, vault)
        if paths_tfidf:
            weighted.append((paths_tfidf, float(tfidf_rrf_weight)))

    return reciprocal_rank_fusion_weighted(weighted, k=rrf_k)


def prf_or_rrf_paths_with_and(
    vault: Path,
    cfg: dict[str, Any],
    question: str,
    *,
    limit: int,
    rrf_k: int = 60,
    path_to_sid: dict[str, str] | None = None,
    tfidf_rrf: bool = True,
    docs_tokens: dict[str, list[str]] | None = None,
    rrf_boost_or: int = 2,
    tfidf_rrf_weight: float = 1.0,
    and_rrf: bool = True,
) -> list[str]:
    """Same as ``prf_or_rrf_paths`` plus optional selective AND query list."""
    from lib.search import FTS5SearchBackend, build_fts_and_query

    base = prf_or_rrf_paths(
        vault,
        cfg,
        question,
        limit=limit,
        rrf_k=rrf_k,
        path_to_sid=path_to_sid,
        tfidf_rrf=tfidf_rrf,
        docs_tokens=docs_tokens,
        rrf_boost_or=rrf_boost_or,
        tfidf_rrf_weight=tfidf_rrf_weight,
    )
    if not and_rrf:
        return base
    q_and = build_fts_and_query(question)
    if not q_and:
        return base
    fts = FTS5SearchBackend(vault, cfg)
    try:
        paths_and = [r.path for r in fts.search(q_and, limit=limit, sanitize_query=False)]
    except Exception:
        return base
    if not paths_and:
        return base
    return reciprocal_rank_fusion([base, paths_and], k=rrf_k)


def refine_head_lexical_overlap(
    question: str,
    paths: list[str],
    vault: Path,
    *,
    head: int = 40,
) -> list[str]:
    """
    Re-score only the first `head` paths by question↔document word overlap (ties
    preserve original order). Keeps BM25/RRF tail intact.
    """
    if len(paths) <= 5:
        return paths
    q_words = {w.lower() for w in re.findall(r"\w+", question, flags=re.UNICODE) if len(w) > 2}
    if not q_words:
        return paths
    head = min(head, len(paths))
    chunk = paths[:head]
    tail = paths[head:]
    scored: list[tuple[float, int, str]] = []
    for orig_i, rel in enumerate(chunk):
        p = vault / rel
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")[:60000]
        except OSError:
            raw = ""
        if raw.startswith("---"):
            end = raw.find("\n---\n", 3)
            if end != -1:
                raw = raw[end + 5 :]
        low = raw.lower()
        doc_words = {w for w in re.findall(r"\w+", low, flags=re.UNICODE) if len(w) > 2}
        overlap = len(q_words & doc_words)
        substr = sum(1 for w in q_words if w in low)
        score = float(overlap) * 2.0 + float(substr) * 0.05
        scored.append((score, orig_i, rel))
    scored.sort(key=lambda x: (-x[0], x[1]))
    new_head = [x[2] for x in scored]
    return new_head + tail


def triple_signal_retrieve_paths(
    vault: Path,
    cfg: dict[str, Any],
    question: str,
    path_to_sid: dict[str, str],
    *,
    limit: int,
    rrf_k: int = 60,
) -> list[str]:
    """
    OR (BM25) + AND (selective terms) + full-corpus lexical overlap, fused with RRF.
    Covers cases where the gold session scores low in FTS but still matches the
    question lexically, and cases where MATCH omits a row from the OR shortlist.
    """
    from lib.search import FTS5SearchBackend, build_fts_and_query

    fts = FTS5SearchBackend(vault, cfg)
    paths_or = [r.path for r in fts.search(question, limit=limit)]
    lists: list[list[str]] = [paths_or]

    q_and = build_fts_and_query(question)
    if q_and:
        try:
            paths_and = [r.path for r in fts.search(q_and, limit=limit, sanitize_query=False)]
        except Exception:
            paths_and = []
        if paths_and:
            lists.append(paths_and)

    all_paths = list(path_to_sid.keys())
    if all_paths:
        lex_order = rerank_paths_lexical(
            question,
            all_paths,
            vault,
            max_paths=len(all_paths),
        )
        lists.append(lex_order)

    if len(lists) == 1:
        return lists[0]
    return reciprocal_rank_fusion(lists, k=rrf_k)


def fuse_paths_rrf_lexical(
    question: str,
    paths: list[str],
    vault: Path,
    *,
    rrf_k: int = 60,
) -> list[str]:
    """
    Combine BM25 order with lexical overlap order via reciprocal rank fusion.
    Pure lexical re-ordering can hurt recall; blending preserves strong BM25 hits
    while surfacing sessions that match many question terms.
    """
    if len(paths) < 2:
        return paths
    lex_order = rerank_paths_lexical(question, list(paths), vault, max_paths=len(paths))
    return reciprocal_rank_fusion([paths, lex_order], k=rrf_k)


def lexical_overlap_score_path(
    question: str,
    vault: Path,
    rel: str,
    *,
    max_chars: int = 80000,
) -> float:
    """
    Single-path lexical score (same formula as ``rerank_paths_lexical``) for
    adaptive / diagnostic use without reordering the full list.
    """
    q_words = {w.lower() for w in re.findall(r"\w+", question, flags=re.UNICODE) if len(w) > 2}
    if not q_words:
        return 0.0
    p = vault / rel
    try:
        raw = p.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        raw = ""
    body = raw
    if body.startswith("---"):
        end = body.find("\n---\n", 3)
        if end != -1:
            body = body[end + 5 :]
    low = body.lower()
    words_in = {w for w in re.findall(r"\w+", low, flags=re.UNICODE) if len(w) > 2}
    overlap = len(q_words & words_in)
    substr_hits = sum(1 for w in q_words if w in low)
    return float(overlap) * 3.0 + float(substr_hits) * 0.15


def adaptive_should_run_llm_rerank(
    question: str,
    paths: list[str],
    vault: Path,
    *,
    head: int = 5,
    lookback: int = 24,
    tail_margin: float = 0.12,
    min_head_lex: float = 3.5,
    max_chars: int = 12000,
) -> bool:
    """
    Cheap heuristic: spend an LLM rerank call when (a) the best lexical match among
    paths ``head..head+lookback`` is competitive with the best among the first
    ``head`` paths (suggests a better session may sit below the RRF top-5), or (b)
    the best lexical score in the top ``head`` is weak (ambiguous / paraphrase-heavy).

    Does **not** use gold labels. When this returns False, BM25/RRF + top-5 lexical
    look strong enough that we skip LLM to avoid regressions on easy questions.
    """
    if not paths:
        return False
    if len(paths) < 2:
        return True
    head = max(1, min(int(head), len(paths)))
    max_h = max(
        lexical_overlap_score_path(question, vault, p, max_chars=max_chars)
        for p in paths[:head]
    )
    end = min(len(paths), head + max(0, int(lookback)))
    if end <= head:
        return max_h < float(min_head_lex)
    max_t = max(
        lexical_overlap_score_path(question, vault, p, max_chars=max_chars)
        for p in paths[head:end]
    )
    if max_h < float(min_head_lex):
        return True
    if max_t >= max_h - float(tail_margin):
        return True
    return False


def rerank_paths_lexical(
    question: str,
    paths: list[str],
    vault: Path,
    *,
    max_paths: int = 200,
    max_chars: int = 80000,
) -> list[str]:
    """
    Re-order retrieval paths by lexical overlap between the question and each
    document body. Helps when BM25 ranks the gold session below the headline top-K
    but still within a larger candidate pool.
    """
    if not paths:
        return paths
    q_words = {w.lower() for w in re.findall(r"\w+", question, flags=re.UNICODE) if len(w) > 2}
    if not q_words:
        return paths
    scored: list[tuple[float, int, str]] = []
    for orig_i, rel in enumerate(paths[:max_paths]):
        p = vault / rel
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")[:max_chars]
        except OSError:
            raw = ""
        body = raw
        if body.startswith("---"):
            end = body.find("\n---\n", 3)
            if end != -1:
                body = body[end + 5 :]
        low = body.lower()
        words_in = {w for w in re.findall(r"\w+", low, flags=re.UNICODE) if len(w) > 2}
        overlap = len(q_words & words_in)
        # Extra weight when a query term appears as substring (handles stems / variants)
        substr_hits = sum(1 for w in q_words if w in low)
        score = float(overlap) * 3.0 + float(substr_hits) * 0.15
        scored.append((score, orig_i, rel))
    scored.sort(key=lambda x: (-x[0], x[1]))
    head = [x[2] for x in scored]
    seen = set(head)
    tail = [p for p in paths if p not in seen]
    return head + tail


def _excerpt_for_llm_rerank(raw: str, max_chars: int, *, mode: str = "head_tail") -> str:
    """Prefer head+tail so answers at the end of long chats are visible to the reranker."""
    raw = raw.replace("\n", " ").strip()
    if len(raw) <= max_chars or mode == "head":
        return raw[:max_chars]
    if mode == "head_tail":
        half = max(max_chars // 2 - 40, 400)
        return raw[:half] + "\n ... \n" + raw[-half:]
    return raw[:max_chars]


def borda_merge_ranks(*ranked_lists: list[str]) -> list[str]:
    """Combine multiple total orderings by Borda count (higher is better)."""
    if not ranked_lists:
        return []
    scores: dict[str, float] = {}
    for rlist in ranked_lists:
        n = len(rlist)
        for rank, path in enumerate(rlist):
            scores[path] = scores.get(path, 0.0) + float(n - rank)
    paths_set = set()
    for rl in ranked_lists:
        paths_set.update(rl)
    return sorted(paths_set, key=lambda p: -scores.get(p, 0.0))


def _llm_rerank_prompt(question: str, n: int, sessions_text: str, *, max_picks: int = 5) -> str:
    return (
        f"Question: {question}\n\n"
        f"You have {n} chat session excerpts labeled Document 1 … Document {n}. "
        f"Each excerpt may show only the start and end of a long session; facts may appear anywhere.\n"
        f"Pick the up to {max_picks} documents whose content is most likely to contain the information needed "
        f"to answer the question (including time references, names, events, preferences, or counts). "
        f"If the question is about a specific entity, date, or prior statement, prefer documents that "
        f"mention them explicitly over generic or tangentially related chats. "
        f"If several sessions are relevant, rank the most informative first.\n"
        f"Reply with ONLY comma-separated integers (document indices), best match first, "
        f"e.g. 5,2,12 or 7,3. No words, no explanation, no markdown.\n\n"
        f"{sessions_text}"
    )


def _strip_rerank_model_output(text: str) -> str:
    """Strip fences, CLI chrome, and labels before parsing doc indices.

    Handles:
    - Markdown code fences (```...```)
    - Codex CLI output: ``[timestamp] codex\\n<answer>\\n[timestamp] tokens used:``
    - Leading labels like ``answer:`` / ``indices:``
    """
    t = (text or "").strip()
    if not t:
        return t
    # Codex CLI JSONL mode: extract agent_message
    if t.startswith("{"):
        for line in t.splitlines():
            line = line.strip()
            if '"agent_message"' in line:
                try:
                    msg = json.loads(line)
                    return (msg.get("msg", {}).get("message", "") or "").strip()
                except (json.JSONDecodeError, AttributeError):
                    pass
    # Codex CLI human-readable: lines start with [timestamp]
    if t.startswith("["):
        answer_lines: list[str] = []
        in_answer = False
        for line in t.splitlines():
            stripped = line.strip()
            if re.match(r"^\[\d{4}-", stripped):
                if "] codex" in stripped.lower():
                    in_answer = True
                    continue
                if in_answer:
                    break
                continue
            if stripped.startswith("--------") or stripped.startswith("workdir:"):
                continue
            if in_answer:
                answer_lines.append(stripped)
        if answer_lines:
            t = "\n".join(answer_lines).strip()
    # Markdown code fences
    if t.startswith("```"):
        lines = t.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    # Leading labels
    for prefix in ("answer:", "indices:", "documents:"):
        if t.lower().startswith(prefix):
            t = t.split(":", 1)[-1].strip()
            break
    return t.strip()


def fuse_llm_rerank_with_original(
    original_paths: list[str],
    llm_paths: list[str],
    *,
    rrf_k: int = 60,
    original_weight: float = 0.35,
) -> list[str]:
    """
    Blend LLM ordering with the pre-LLM retrieval order via weighted RRF.
    Stabilizes cases where the LLM reordering hurts BM25/PRF quality.
    """
    if original_weight <= 0 or not original_paths or not llm_paths:
        return llm_paths
    ow = min(float(original_weight), 2.0)
    return reciprocal_rank_fusion_weighted(
        [(llm_paths, 1.0), (original_paths, ow)],
        k=rrf_k,
    )


def _parse_rerank_doc_indices(text: str, n: int, *, max_picks: int = 5) -> list[int]:
    picked: list[int] = []
    for tok in re.findall(r"\b\d+\b", text):
        idx = int(tok)
        if 1 <= idx <= n and idx not in picked:
            picked.append(idx)
        if len(picked) >= max_picks:
            break
    return picked


def _default_rerank_cli_argv(invoke: str) -> list[str]:
    """Non-interactive defaults; override via ``rerank_llm.cli_argv`` in config."""
    if invoke == "claude_cli":
        return ["claude", "--print", "--tools", "", "--no-session-persistence"]
    if invoke == "codex_cli":
        return [
            "codex", "exec",
            "-s", "read-only",
            "--skip-git-repo-check",
            "-",
        ]
    return []


def _openai_chat_message_text(msg: dict[str, Any]) -> str:
    """Normalize OpenAI chat message content (string or multimodal parts)."""
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts: list[str] = []
        for p in c:
            if isinstance(p, dict) and p.get("type") == "text":
                parts.append(str(p.get("text", "")))
            elif isinstance(p, dict) and "text" in p:
                parts.append(str(p["text"]))
        return "".join(parts)
    return ""


def _rerank_paths_llm_openai_api(
    prompt: str,
    *,
    api_key: str,
    model: str,
    n_paths: int,
    paths: list[str],
    max_picks: int = 5,
) -> list[str] | None:
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 256,
            "temperature": 0,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
        msg = (result.get("choices") or [{}])[0].get("message") or {}
        raw = _strip_rerank_model_output(_openai_chat_message_text(msg))
    except (urllib.error.URLError, KeyError, ValueError, IndexError, OSError, TypeError) as exc:
        print(f"[rerank] OpenAI API error: {exc}", file=sys.stderr)
        return None
    picked = _parse_rerank_doc_indices(raw, n_paths, max_picks=max_picks)
    if not picked:
        return None
    head = [paths[i - 1] for i in picked]
    tail = [p for p in paths if p not in head]
    return head + tail


def _rerank_paths_llm_anthropic_api(
    prompt: str,
    *,
    api_key: str,
    model: str,
    n_paths: int,
    paths: list[str],
    max_picks: int = 5,
) -> list[str] | None:
    payload = json.dumps(
        {
            "model": model,
            "max_tokens": 256,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read())
        raw = _strip_rerank_model_output(result["content"][0]["text"])
    except (urllib.error.URLError, KeyError, ValueError, IndexError, OSError, TypeError) as exc:
        print(f"[rerank] Anthropic API error: {exc}", file=sys.stderr)
        return None
    picked = _parse_rerank_doc_indices(raw, n_paths, max_picks=max_picks)
    if not picked:
        return None
    head = [paths[i - 1] for i in picked]
    tail = [p for p in paths if p not in head]
    return head + tail


def _rerank_paths_llm_cli(
    prompt: str,
    argv: list[str],
    *,
    timeout_s: int,
    n_paths: int,
    paths: list[str],
    max_picks: int = 5,
) -> list[str] | None:
    if not argv:
        return None
    try:
        proc = subprocess.run(
            argv,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            env=os.environ.copy(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"[rerank] CLI error: {exc}", file=sys.stderr)
        return None
    raw = _strip_rerank_model_output((proc.stdout or "").strip())
    if proc.returncode != 0 and not raw:
        raw = _strip_rerank_model_output((proc.stderr or "").strip())
    picked = _parse_rerank_doc_indices(raw, n_paths, max_picks=max_picks)
    if not picked:
        return None
    head = [paths[i - 1] for i in picked]
    tail = [p for p in paths if p not in head]
    return head + tail


def rerank_paths_cross_encoder(
    question: str,
    paths: list[str],
    vault: Path,
    *,
    model_name: str = "mixedbread-ai/mxbai-rerank-large-v1",
    max_candidates: int = 80,
    max_chars: int = 10000,
    top_k: int = 10,
) -> list[str]:
    """
    Re-rank candidate paths using a local cross-encoder model (no API calls).
    Requires ``sentence-transformers`` (``pip install sentence-transformers``).
    Falls back to the original order if the dependency is missing.
    """
    if not paths:
        return paths
    try:
        from sentence_transformers import CrossEncoder
    except ImportError:
        return paths
    ce = CrossEncoder(model_name)
    n = min(len(paths), max(5, max_candidates))
    pairs: list[tuple[str, str]] = []
    for rel in paths[:n]:
        p = vault / rel
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            raw = ""
        if raw.startswith("---"):
            fm_end = raw.find("\n---\n", 3)
            if fm_end != -1:
                raw = raw[fm_end + 5:]
        raw = raw.replace("\n", " ").strip()[:max_chars]
        pairs.append((question, raw))
    scores = ce.predict(pairs)
    indexed = sorted(enumerate(scores), key=lambda x: -x[1])
    reranked = [paths[i] for i, _ in indexed[:top_k]]
    seen = set(reranked)
    tail = [p for p in paths if p not in seen]
    return reranked + tail


def _resolve_auto_invoke(api_key: str) -> str | None:
    """Pick the best available rerank backend: CLIs first (free), then APIs."""
    import shutil

    if shutil.which("claude"):
        return "claude_cli"
    if shutil.which("codex"):
        return "codex_cli"
    if api_key:
        return "anthropic_api"
    oai = os.environ.get("OPENAI_API_KEY", "")
    if oai:
        return "openai_api"
    print("[rerank] auto: no CLI or API key found — skipping rerank", file=sys.stderr)
    return None


def rerank_paths_llm(
    question: str,
    paths: list[str],
    vault: Path,
    *,
    api_key: str = "",
    invoke: str = "anthropic_api",
    model: str = "claude-sonnet-4-6",
    max_chars: int = 2800,
    max_candidates: int = 72,
    max_picks: int = 5,
    excerpt_mode: str = "head_tail",
    cli_argv: list[str] | None = None,
    cli_timeout_s: int = 180,
    fuse_original_rrf: bool = False,
    fuse_original_weight: float = 0.35,
    fuse_rrf_k: int = 60,
    session_dedup: bool = False,
    path_to_sid: dict[str, str] | None = None,
) -> list[str]:
    """
    Ask an LLM for up to 5 document indices (best first) among the first
    ``max_candidates`` paths.

    ``invoke``:
      - ``auto`` — try ``claude_cli``, then ``codex_cli``, then ``anthropic_api``,
        then ``openai_api``; picks the first available backend.
      - ``anthropic_api`` — Messages API (needs ``ANTHROPIC_API_KEY`` or ``api_key_env``).
        Models: e.g. ``claude-sonnet-4-6``, ``claude-opus-4-6`` (see Anthropic model docs).
      - ``openai_api`` — Chat Completions (needs ``OPENAI_API_KEY`` or ``api_key_env``).
        Models: e.g. ``gpt-5.4`` or snapshot ``gpt-5.4-2026-03-05``.
      - ``claude_cli`` / ``codex_cli`` — local CLI; prompt on stdin.
        Set ``cli_argv`` to match your installed CLI.
      - ``custom_cli`` — ``cli_argv`` required (e.g. ``["my-cli", "--prompt", "-"]``).
    """
    if not paths:
        return paths
    original_paths = list(paths)
    invoke = (invoke or "auto").strip().lower()
    if invoke == "auto":
        invoke = _resolve_auto_invoke(api_key)
        if invoke is None:
            return paths
    if invoke == "anthropic_api" and not api_key:
        return paths
    if invoke == "openai_api" and not api_key:
        return paths
    if invoke == "custom_cli" and not cli_argv:
        return paths
    if invoke in ("claude_cli", "codex_cli") and not cli_argv:
        cli_argv = _default_rerank_cli_argv(invoke)
        if not cli_argv:
            return paths

    n = min(len(paths), max(5, max_candidates))

    def _maybe_fuse(out: list[str] | None) -> list[str]:
        if out is None:
            return paths
        if not fuse_original_rrf or fuse_original_weight <= 0:
            return out
        return fuse_llm_rerank_with_original(
            original_paths,
            out,
            rrf_k=int(fuse_rrf_k),
            original_weight=float(fuse_original_weight),
        )

    # Session dedup: merge paths belonging to the same session into one document block
    # so the LLM ranks sessions, not individual paths. After LLM returns indices,
    # expand back to the original path ordering.
    if session_dedup and path_to_sid:
        seen_sids: dict[str, int] = {}
        session_blocks: list[tuple[str, list[str]]] = []  # (merged_text, [paths])
        for rel in paths[:n]:
            sid = path_to_sid.get(rel.replace("\\", "/"), rel)
            p = vault / rel
            try:
                raw = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                raw = ""
            if raw.startswith("---"):
                fm_end = raw.find("\n---\n", 3)
                if fm_end != -1:
                    raw = raw[fm_end + 5:]
            text = _excerpt_for_llm_rerank(raw, max_chars, mode=excerpt_mode)
            if sid in seen_sids:
                idx = seen_sids[sid]
                old_text, old_paths = session_blocks[idx]
                session_blocks[idx] = (old_text + "\n\n" + text, old_paths + [rel])
            else:
                seen_sids[sid] = len(session_blocks)
                session_blocks.append((text, [rel]))
        blocks = []
        dedup_paths: list[list[str]] = []
        for i, (text, block_paths) in enumerate(session_blocks):
            label = path_to_sid.get(block_paths[0].replace("\\", "/"), block_paths[0])
            blocks.append(f"Document {i + 1} (session {label}):\n{text}")
            dedup_paths.append(block_paths)
        n_dedup = len(blocks)
        sessions_text = "\n\n".join(blocks)
        prompt = _llm_rerank_prompt(question, n_dedup, sessions_text, max_picks=max_picks)

        def _expand_dedup(out_indices: list[int] | None) -> list[str] | None:
            if out_indices is None:
                return None
            head: list[str] = []
            for idx in out_indices:
                if 1 <= idx <= n_dedup:
                    head.extend(dedup_paths[idx - 1])
            seen = set(head)
            tail = [p for p in paths if p not in seen]
            return head + tail

        def _dispatch_dedup(raw_text: str) -> list[str] | None:
            picked = _parse_rerank_doc_indices(raw_text, n_dedup, max_picks=max_picks)
            return _expand_dedup(picked) if picked else None

        # Dispatch with dedup expansion
        if invoke == "anthropic_api":
            payload = json.dumps(
                {"model": model, "max_tokens": 256,
                 "messages": [{"role": "user", "content": prompt}]}
            ).encode("utf-8")
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages", data=payload,
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=90) as resp:
                    result = json.loads(resp.read())
                raw_out = _strip_rerank_model_output(result["content"][0]["text"])
            except (urllib.error.URLError, KeyError, ValueError, IndexError, OSError, TypeError) as exc:
                print(f"[rerank-dedup] Anthropic API error: {exc}", file=sys.stderr)
                return _maybe_fuse(None)
            return _maybe_fuse(_dispatch_dedup(raw_out))

        if invoke == "openai_api":
            payload = json.dumps(
                {"model": model, "messages": [{"role": "user", "content": prompt}],
                 "max_tokens": 256, "temperature": 0}
            ).encode("utf-8")
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions", data=payload,
                headers={"Authorization": f"Bearer {api_key}",
                         "content-type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    result = json.loads(resp.read())
                msg = (result.get("choices") or [{}])[0].get("message") or {}
                raw_out = _strip_rerank_model_output(_openai_chat_message_text(msg))
            except (urllib.error.URLError, KeyError, ValueError, IndexError, OSError, TypeError) as exc:
                print(f"[rerank-dedup] OpenAI API error: {exc}", file=sys.stderr)
                return _maybe_fuse(None)
            return _maybe_fuse(_dispatch_dedup(raw_out))

        argv = list(cli_argv or [])
        if not argv:
            return paths
        try:
            proc = subprocess.run(
                argv, input=prompt, text=True, capture_output=True,
                timeout=int(cli_timeout_s), env=os.environ.copy())
        except (OSError, subprocess.TimeoutExpired):
            return _maybe_fuse(None)
        raw_out = _strip_rerank_model_output((proc.stdout or "").strip())
        if proc.returncode != 0 and not raw_out:
            raw_out = _strip_rerank_model_output((proc.stderr or "").strip())
        return _maybe_fuse(_dispatch_dedup(raw_out))

    # Standard path-level reranking (no session dedup)
    blocks: list[str] = []
    for i, rel in enumerate(paths[:n]):
        p = vault / rel
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            raw = ""
        if raw.startswith("---"):
            fm_end = raw.find("\n---\n", 3)
            if fm_end != -1:
                raw = raw[fm_end + 5:]
        text = _excerpt_for_llm_rerank(raw, max_chars, mode=excerpt_mode)
        blocks.append(f"Document {i + 1} ({rel}):\n{text}")
    sessions_text = "\n\n".join(blocks)
    prompt = _llm_rerank_prompt(question, n, sessions_text, max_picks=max_picks)

    if invoke == "anthropic_api":
        out = _rerank_paths_llm_anthropic_api(
            prompt, api_key=api_key, model=model, n_paths=n, paths=paths,
            max_picks=max_picks,
        )
        return _maybe_fuse(out)

    if invoke == "openai_api":
        out = _rerank_paths_llm_openai_api(
            prompt, api_key=api_key, model=model, n_paths=n, paths=paths,
            max_picks=max_picks,
        )
        return _maybe_fuse(out)

    argv = list(cli_argv or [])
    out = _rerank_paths_llm_cli(
        prompt,
        argv,
        timeout_s=int(cli_timeout_s),
        n_paths=n,
        paths=paths,
        max_picks=max_picks,
    )
    return _maybe_fuse(out)


def git_sha_short(repo: Path | None = None) -> str:
    """Best-effort short git SHA for benchmark lineage (empty if not a git checkout)."""
    try:
        root = repo
        if root is None:
            from lib.paths import plugin_root

            root = plugin_root()
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout.strip()[:12]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def build_benchmark_record_meta(
    cfg: dict[str, Any],
    *,
    suite: str,
    backend: str,
    compressor: str,
    summary: dict[str, Any],
    limit: int = 0,
    llm_flag: bool = False,
    rerank_invoke: str | None = None,
) -> dict[str, Any]:
    ch = summary.get("config_hash") or config_hash(cfg)
    meta: dict[str, Any] = {
        "suite": suite,
        "config_hash": ch,
        "limit": int(limit),
        "llm_flag": llm_flag,
        "rerank_invoke": rerank_invoke or "",
        "git_sha": git_sha_short(),
    }
    fbc = summary.get("failure_bucket_counts")
    if isinstance(fbc, dict):
        meta["failure_bucket_counts"] = fbc
    return meta


def append_repo_benchmark_runs_jsonl(
    cfg: dict[str, Any],
    *,
    summary: dict[str, Any],
    vault: Path,
) -> Path | None:
    """Append one chart-friendly line under repo docs/memory/benchmarks/metrics/runs.jsonl when enabled."""
    bcfg = cfg.get("benchmark") or {}
    if not bcfg.get("append_repo_runs_jsonl", False):
        return None
    try:
        from lib.paths import plugin_root

        root = plugin_root()
    except Exception:
        return None
    rel = str(
        bcfg.get(
            "repo_runs_jsonl_path",
            "docs/memory/benchmarks/metrics/runs.jsonl",
        )
    )
    path = (root / rel).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    rl = ((cfg.get("benchmark") or {}).get("search") or {}).get("rerank_llm") or {}
    line = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "vault": str(vault),
        **{k: summary[k] for k in summary if k in (
            "suite", "backend", "compressor", "questions", "elapsed_s", "config_hash",
            "recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10",
            "ndcg_at_5", "ndcg_at_10", "failures", "failure_bucket_counts", "token_ratio_mean",
            "llm_adaptive_skips",
        )},
        "llm_flag": str(os.environ.get("LLM_WIKI_BENCHMARK_LLM", "")).lower()
        in ("1", "true", "yes"),
        "rerank_invoke": str(rl.get("invoke", "")),
    }
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, default=str) + "\n")
    except OSError:
        return None
    return path


def write_benchmark_run_sidecar(
    vault: Path,
    cfg: dict[str, Any],
    *,
    suite: str,
    summary: dict[str, Any],
    result: dict[str, Any],
) -> Path | None:
    """Optional JSON snapshot under .benchmarks/runs/."""
    bcfg = cfg.get("benchmark") or {}
    if not bcfg.get("write_run_sidecar", True):
        return None
    results_dir = vault / bcfg.get("results_dir", ".benchmarks")
    runs_dir = results_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    h = str(summary.get("config_hash", "nohash"))[:12]
    name = f"{ts}_{suite}_{summary.get('backend', '')}_{h}.json"
    path = runs_dir / name
    payload = {
        "suite": suite,
        "summary": summary,
        "failure_count": len(result.get("failures") or []),
    }
    try:
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    except OSError:
        return None
    return path


def record_benchmark_metrics(
    vault: Path,
    cfg: dict[str, Any],
    *,
    suite: str,
    backend: str,
    compressor: str,
    metrics: dict[str, float],
    meta: dict[str, Any] | None = None,
) -> None:
    bcfg = cfg.get("benchmark") or {}
    if not bcfg.get("auto_record_metrics", True):
        return
    cfg_m = deep_merge(cfg, {"metrics": {"enabled": True}})
    m = MetricsRecorder(vault, cfg_m)
    if not m.enabled:
        return
    tags = [suite, backend, compressor]
    for key, val in metrics.items():
        m.record(
            f"benchmark.{suite}.{key}",
            val,
            meta={**(meta or {}), "backend": backend, "compressor": compressor},
            tags=tags,
        )


def config_hash(cfg: dict[str, Any]) -> str:
    """Stable short hash of benchmark-relevant config for logs."""
    sub = {k: cfg.get(k) for k in ("benchmark", "mcp", "performance")}
    blob = json.dumps(sub, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def ensure_vault_config(vault: Path, cfg: dict[str, Any]) -> None:
    save_config(vault, cfg)
    (vault / "wiki").mkdir(parents=True, exist_ok=True)
    (vault / "raw").mkdir(parents=True, exist_ok=True)
