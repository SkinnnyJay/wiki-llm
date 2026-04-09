"""Shared benchmark harness: scoring, hybrid fusion, vault layout, metrics."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
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


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    *,
    k: int = 60,
) -> list[str]:
    """RRF over path identifiers. Each list is paths best-first."""
    scores: dict[str, float] = {}
    for rlist in ranked_lists:
        for rank, path in enumerate(rlist):
            scores[path] = scores.get(path, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.keys(), key=lambda p: -scores[p])


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


def _llm_rerank_prompt(question: str, n: int, sessions_text: str) -> str:
    return (
        f"Question: {question}\n\n"
        f"You have {n} excerpts (documents 1-{n}). Each may show start and end of a long session. "
        f"Which up to 5 documents most likely contain the facts needed to answer the question? "
        f"Reply with ONLY comma-separated numbers, best first, e.g. 5,2,12. "
        f"No words.\n\n{sessions_text}"
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
        return ["claude", "-p", "-"]
    if invoke == "codex_cli":
        return ["codex", "exec", "-"]
    return []


def _rerank_paths_llm_anthropic_api(
    prompt: str,
    *,
    api_key: str,
    model: str,
    n_paths: int,
    paths: list[str],
) -> list[str] | None:
    payload = json.dumps(
        {
            "model": model,
            "max_tokens": 128,
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
        raw = result["content"][0]["text"].strip()
    except (urllib.error.URLError, KeyError, ValueError, IndexError, OSError, TypeError):
        return None
    picked = _parse_rerank_doc_indices(raw, n_paths)
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
    except (OSError, subprocess.TimeoutExpired):
        return None
    raw = (proc.stdout or "").strip()
    if proc.returncode != 0 and not raw:
        raw = (proc.stderr or "").strip()
    picked = _parse_rerank_doc_indices(raw, n_paths)
    if not picked:
        return None
    head = [paths[i - 1] for i in picked]
    tail = [p for p in paths if p not in head]
    return head + tail


def rerank_paths_llm(
    question: str,
    paths: list[str],
    vault: Path,
    *,
    api_key: str = "",
    invoke: str = "anthropic_api",
    model: str = "claude-3-5-haiku-20241022",
    max_chars: int = 2800,
    max_candidates: int = 72,
    excerpt_mode: str = "head_tail",
    cli_argv: list[str] | None = None,
    cli_timeout_s: int = 180,
) -> list[str]:
    """
    Ask an LLM for up to 5 document indices (best first) among the first
    ``max_candidates`` paths.

    ``invoke``:
      - ``anthropic_api`` — Messages API (needs ``ANTHROPIC_API_KEY`` or config env).
      - ``claude_cli`` / ``codex_cli`` — local CLI; prompt on stdin (default argv
        ends with ``-``). Set ``cli_argv`` to match your installed CLI.
      - ``custom_cli`` — ``cli_argv`` required (e.g. ``["my-cli", "--prompt", "-"]``).
    """
    if not paths:
        return paths
    invoke = (invoke or "anthropic_api").strip().lower()
    if invoke == "anthropic_api" and not api_key:
        return paths
    if invoke == "custom_cli" and not cli_argv:
        return paths
    if invoke in ("claude_cli", "codex_cli") and not cli_argv:
        cli_argv = _default_rerank_cli_argv(invoke)
        if not cli_argv:
            return paths

    n = min(len(paths), max(5, max_candidates))
    blocks: list[str] = []
    for i, rel in enumerate(paths[:n]):
        p = vault / rel
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            raw = ""
        text = _excerpt_for_llm_rerank(raw, max_chars, mode=excerpt_mode)
        blocks.append(f"Document {i + 1} ({rel}):\n{text}")
    sessions_text = "\n\n".join(blocks)
    prompt = _llm_rerank_prompt(question, n, sessions_text)

    if invoke == "anthropic_api":
        out = _rerank_paths_llm_anthropic_api(
            prompt, api_key=api_key, model=model, n_paths=n, paths=paths
        )
        return out if out is not None else paths

    argv = list(cli_argv or [])
    out = _rerank_paths_llm_cli(
        prompt,
        argv,
        timeout_s=int(cli_timeout_s),
        n_paths=n,
        paths=paths,
    )
    return out if out is not None else paths


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
