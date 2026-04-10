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

from benchmarks.lme_bench import (
    _classify_lme_failure,
    _gold_sid_in_paths,
    analyze_lme_failures_log,
    format_lme_failures_analysis,
)
from benchmarks.bench_harness import (
    _bench_doc_tokens,
    _parse_rerank_doc_indices,
    _strip_rerank_model_output,
    adaptive_should_run_llm_rerank,
    borda_merge_ranks,
    fuse_llm_rerank_with_original,
    lexical_overlap_score_path,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank_fusion_weighted,
    rerank_paths_llm,
    tfidf_corpus_rank_from_tokens,
    _excerpt_for_llm_rerank,
)
from lib.compressors import get_compressor
from lib.rank_fusion import reciprocal_rank_fusion
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


def test_strip_rerank_model_output():
    assert _strip_rerank_model_output("```\n3,1,5\n```") == "3,1,5"
    assert _strip_rerank_model_output("Answer: 7,2") == "7,2"


def test_fuse_llm_rerank_with_original():
    orig = ["a.md", "b.md", "c.md", "d.md"]
    llm = ["c.md", "a.md", "b.md", "d.md"]
    fused = fuse_llm_rerank_with_original(orig, llm, original_weight=0.5, rrf_k=60)
    assert len(fused) == 4
    assert set(fused) == set(orig)


def _bench_md(root: Path, rel: str, body: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntitle: t\n---\n\n{body}", encoding="utf-8")


def test_lexical_overlap_score_path_positive(tmp_path):
    _bench_md(tmp_path, "raw/bench/a.md", "alpha beta gamma " * 80)
    s = lexical_overlap_score_path(
        "alpha beta gamma question",
        tmp_path,
        "raw/bench/a.md",
        max_chars=4000,
    )
    assert s > 5.0


def test_compute_rerank_confidence_in_range(tmp_path):
    q = "alpha beta gamma delta epsilon"
    for i in range(5):
        _bench_md(tmp_path, f"raw/bench/h{i}.md", q + " " + "filler " * 40)
    for j in range(5):
        _bench_md(tmp_path, f"raw/bench/t{j}.md", "zzz unrelated noise " * 60)
    paths = [f"raw/bench/h{i}.md" for i in range(5)] + [
        f"raw/bench/t{j}.md" for j in range(5)
    ]
    from benchmarks.bench_harness import compute_rerank_confidence

    c = compute_rerank_confidence(
        q,
        paths,
        tmp_path,
        head=5,
        lookback=5,
        tail_margin=0.12,
        min_head_lex=3.5,
    )
    assert 0.0 <= c <= 1.0


def test_adaptive_skips_llm_when_head_strong_tail_weak(tmp_path):
    q = "alpha beta gamma delta epsilon"
    for i in range(5):
        _bench_md(tmp_path, f"raw/bench/h{i}.md", q + " " + "filler " * 40)
    for j in range(5):
        _bench_md(tmp_path, f"raw/bench/t{j}.md", "zzz unrelated noise " * 60)
    paths = [f"raw/bench/h{i}.md" for i in range(5)] + [
        f"raw/bench/t{j}.md" for j in range(5)
    ]
    assert adaptive_should_run_llm_rerank(
        q,
        paths,
        tmp_path,
        head=5,
        lookback=5,
        tail_margin=0.12,
        min_head_lex=3.5,
    ) is False


def test_analyze_lme_failures_jsonl(tmp_path):
    p = tmp_path / "lme_failures.jsonl"
    p.write_text(
        '{"question_id":"q1","failure_bucket":"R","question":"hello","gold_in_pool_pre_llm":true,'
        '"llm_invoked":true,"llm_adaptive_skip":false,"llm_rerank_reordered":false}\n',
        encoding="utf-8",
    )
    s = analyze_lme_failures_log(p)
    assert s["failure_count"] == 1
    assert s["failure_bucket_counts"]["R"] == 1
    assert s["question_ids"] == ["q1"]
    text = format_lme_failures_analysis(s)
    assert "q1" in text and "[R]" in text


def test_adaptive_runs_llm_when_tail_competes(tmp_path):
    q = "alpha beta gamma"
    for i in range(4):
        _bench_md(tmp_path, f"raw/bench/w{i}.md", "weak doc " * 50)
    _bench_md(tmp_path, "raw/bench/strong_tail.md", q + " " + "extra " * 80)
    paths = [f"raw/bench/w{i}.md" for i in range(4)] + ["raw/bench/strong_tail.md"]
    assert adaptive_should_run_llm_rerank(
        q,
        paths,
        tmp_path,
        head=4,
        lookback=4,
        tail_margin=0.05,
        min_head_lex=10.0,
    ) is True


def test_rerank_llm_skips_when_no_api_for_anthropic():
    out = rerank_paths_llm(
        "q",
        ["a.md"],
        Path("/nonexistent-vault-xyz"),
        api_key="",
        invoke="anthropic_api",
    )
    assert out == ["a.md"]


def test_rerank_llm_skips_when_no_api_for_openai():
    out = rerank_paths_llm(
        "q",
        ["a.md"],
        Path("/nonexistent-vault-xyz"),
        api_key="",
        invoke="openai_api",
        model="gpt-5.4",
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


def test_classify_lme_failure_buckets():
    gold = {"a"}
    assert _classify_lme_failure(gold, True, True, want_llm=False, can_run=False, env_on=False) == ""
    assert _classify_lme_failure(gold, False, False, want_llm=True, can_run=False, env_on=True) == "L"
    assert _classify_lme_failure(gold, False, False, want_llm=False, can_run=False, env_on=False) == "P"
    assert _classify_lme_failure(gold, True, False, want_llm=False, can_run=False, env_on=False) == "R"
    assert _classify_lme_failure({"a", "b"}, True, False, want_llm=False, can_run=False, env_on=False) == "M"


def test_gold_sid_in_paths():
    pt = {"x/a.md": "S1", "x/b.md": "S2"}
    assert _gold_sid_in_paths(["x/a.md"], {"S1"}, pt) is True
    assert _gold_sid_in_paths(["x/b.md"], {"S1"}, pt) is False


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

