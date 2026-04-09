"""Unit tests for benchmark scoring helpers and compressors."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from benchmarks.bench_harness import (
    _bench_doc_tokens,
    _parse_rerank_doc_indices,
    borda_merge_ranks,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank_fusion,
    reciprocal_rank_fusion_weighted,
    rerank_paths_llm,
    tfidf_corpus_rank_from_tokens,
    _excerpt_for_llm_rerank,
)
from lib.compressors import get_compressor
from lib.search import prepare_fts5_match_query


def test_recall_at_k_hit():
    assert recall_at_k([2, 0, 1], {1}, k=3) == 1.0


def test_recall_at_k_miss():
    assert recall_at_k([0, 2, 3], {1}, k=3) == 0.0


def test_ndcg_perfect():
    # Rankings: gold at position 0 → NDCG@3 should be 1.0
    assert ndcg_at_k([1, 0, 2], {1}, k=3) == pytest.approx(1.0)


def test_rrf_fusion():
    fused = reciprocal_rank_fusion([["a", "b"], ["b", "c"]], k=60)
    assert fused[0] == "b"


def test_rrf_weighted_downranks_second_list():
    # Same as unweighted would prefer "x" from two lists; halving list2 lets list1 win.
    w = reciprocal_rank_fusion_weighted(
        [(["x", "y"], 1.0), (["y", "x"], 0.5)],
        k=60,
    )
    assert w[0] == "x"


def test_borda_prefers_consensus_top():
    a = ["x", "y", "z"]
    b = ["y", "x", "z"]
    m = borda_merge_ranks(a, b)
    assert m[0] in ("x", "y")


def test_excerpt_head_tail_preserves_ends():
    long = "START" + "x" * 5000 + "ENDMARK"
    ex = _excerpt_for_llm_rerank(long, 200, mode="head_tail")
    assert "START" in ex and "ENDMARK" in ex


def test_bench_doc_tokens_head_tail_sees_tail_word(tmp_path):
    # Pad so only the tail window (not the head-only prefix) contains the marker.
    body = "aaa " * 2000 + "bbb " * 2000 + " tailuniquexyz endpad"
    md = tmp_path / "raw" / "bench"
    md.mkdir(parents=True)
    f = md / "t.md"
    f.write_text("---\ntitle: x\n---\n\n" + body, encoding="utf-8")
    toks_ht = _bench_doc_tokens(tmp_path, "raw/bench/t.md", 4000, head_tail=True)
    toks_head = _bench_doc_tokens(tmp_path, "raw/bench/t.md", 4000, head_tail=False)
    assert "tailuniquexyz" in toks_ht
    assert "tailuniquexyz" not in toks_head


def test_parse_rerank_doc_indices():
    assert _parse_rerank_doc_indices("5,2,12", 20) == [5, 2, 12]
    assert _parse_rerank_doc_indices("best 3 then 1", 5) == [3, 1]


def test_rerank_llm_skips_when_no_api_for_anthropic():
    out = rerank_paths_llm(
        "q",
        ["a.md"],
        Path("/nonexistent-vault-xyz"),
        api_key="",
        invoke="anthropic_api",
    )
    assert out == ["a.md"]


def test_tfidf_rank_prefers_matching_doc():
    docs = {
        "a.md": ["hello", "world", "foo"],
        "b.md": ["degree", "graduate", "computer", "science", "degree"],
    }
    r = tfidf_corpus_rank_from_tokens("What degree did I graduate with?", docs)
    assert r[0] == "b.md"


def test_prepare_fts5_strips_punctuation():
    q = "What degree did I graduate with?"
    safe = prepare_fts5_match_query(q)
    assert "?" not in safe
    assert " OR " in safe or safe


@pytest.mark.parametrize("name", ["raw", "steno", "prune", "extract", "compact"])
def test_compressor_smoke(name: str):
    cfg = {"benchmark": {}}
    c = get_compressor(name, cfg)
    text = "The quick brown fox jumps over the lazy dog. Alice visited Paris in 2024."
    out = c.compress(text, metadata={})
    assert isinstance(out, str)
    assert len(out) >= 0
    st = c.stats(text, out)
    assert "ratio" in st

