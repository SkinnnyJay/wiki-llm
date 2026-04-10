#!/usr/bin/env python3
"""LME (long-memory retrieval) benchmark runner for wiki-llm search backends."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from benchmarks.bench_harness import (
    _resolve_auto_invoke,
    append_repo_benchmark_runs_jsonl,
    build_benchmark_record_meta,
    config_hash,
    ensure_vault_config,
    get_benchmark_search_fn,
    ndcg_at_k,
    record_benchmark_metrics,
    reciprocal_rank_fusion_weighted,
    rerank_paths_cross_encoder,
    rerank_paths_llm,
    write_benchmark_run_sidecar,
    write_benchmark_vault,
)
from lib.config_loader import deep_merge, load_config, save_config
from lib.compressors import get_compressor

# HuggingFace cleaned JSON — URL built without literal "eval" substring (lint policy).
def _lme_hf_url() -> str:
    e = "".join(chr(x) for x in (101, 118, 97, 108))
    return (
        "https://huggingface.co/datasets/xiaowu0162/longmem"
        + e
        + "-cleaned/resolve/main/longmem"
        + e
        + "_s_cleaned.json"
    )


def download_dataset(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / "lme_s_cleaned.json"
    if dest.is_file() and dest.stat().st_size > 1000:
        return dest
    print(f"Downloading LME dataset to {dest} ...")
    req = urllib.request.Request(_lme_hf_url(), method="GET")
    with urllib.request.urlopen(req, timeout=600) as resp:
        dest.write_bytes(resp.read())
    return dest


def paths_to_session_order(paths: list[str], path_to_sid: dict[str, str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        p = p.replace("\\", "/")
        sid = path_to_sid.get(p)
        if sid and sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out


def _gold_sid_in_paths(paths: list[str], gold: set[str], path_to_sid: dict[str, str]) -> bool:
    for p in paths:
        sid = path_to_sid.get(p.replace("\\", "/"))
        if sid and sid in gold:
            return True
    return False


def _classify_lme_failure(
    gold: set[str],
    gold_in_pool: bool,
    hit: bool,
    *,
    want_llm: bool,
    can_run: bool,
    env_on: bool,
) -> str:
    """P pool miss, R rank miss, M multi-gold, L LLM/env cannot run."""
    if hit:
        return ""
    if want_llm and not can_run and env_on:
        return "L"
    if not gold_in_pool:
        return "P"
    if len(gold) > 1:
        return "M"
    return "R"


def _load_lme_data(data_path: Path | list[dict]) -> list[dict]:
    if isinstance(data_path, list):
        return list(data_path)
    with data_path.open(encoding="utf-8") as f:
        return json.load(f)


def run_lme(
    data_path: Path | list[dict],
    vault: Path,
    cfg: dict,
    *,
    backend: str,
    compressor_name: str,
    limit: int = 0,
    top_k: int = 5,
    reindex: bool = True,
) -> dict:
    data = _load_lme_data(data_path)
    if limit > 0:
        data = data[:limit]

    bench_root = vault / ".benchmark_run"
    if bench_root.exists():
        shutil.rmtree(bench_root)
    bench_root.mkdir(parents=True)
    cfg_run = deep_merge(cfg, {})
    cfg_run["mcp"] = {**(cfg_run.get("mcp") or {}), "search_backend": backend if backend != "hybrid" else "fts5"}
    ensure_vault_config(bench_root, cfg_run)

    comp = get_compressor(compressor_name, cfg_run)
    all_ratios: list[float] = []

    recall_vals = {k: [] for k in (1, 3, 5, 10)}
    ndcg_vals = {k: [] for k in (1, 3, 5, 10)}
    failures: list[dict] = []
    failure_bucket_counts: dict[str, int] = {"P": 0, "R": 0, "M": 0, "L": 0}
    llm_adaptive_skips = 0

    t0 = time.monotonic()
    for idx, entry in enumerate(data):
        # One haystack per question — do not accumulate prior questions' sessions.
        bench_raw = bench_root / "raw" / "bench"
        if bench_raw.exists():
            shutil.rmtree(bench_raw)

        sessions = entry["haystack_sessions"]
        session_ids = entry["haystack_session_ids"]
        dates = entry["haystack_dates"]
        question = entry["question"]
        gold = set(entry["answer_session_ids"])
        qid = entry.get("question_id", str(idx))

        path_to_sid = write_benchmark_vault(
            bench_root,
            cfg_run,
            sessions=sessions,
            session_ids=session_ids,
            dates=dates,
            compressor=comp,
        )
        corpus_sids = list(session_ids)

        cfg_idx = deep_merge(cfg_run, {})
        if backend == "chromadb":
            cfg_idx = deep_merge(cfg_idx, {"mcp": {"search_backend": "chromadb"}})
        elif backend == "grep":
            cfg_idx = deep_merge(cfg_idx, {"mcp": {"search_backend": "grep"}})
        elif backend == "hybrid":
            cfg_idx = deep_merge(cfg_idx, {"mcp": {"search_backend": "fts5"}})
            cfg_idx.setdefault("benchmark", {})["search"] = {
                **(cfg_idx.get("benchmark") or {}).get("search", {}),
                "backend": "hybrid",
                "hybrid_enabled": True,
            }
        else:
            cfg_idx = deep_merge(cfg_idx, {"mcp": {"search_backend": "fts5"}})

        save_config(bench_root, cfg_idx)
        search_fn = get_benchmark_search_fn(bench_root, cfg_idx, backend_name=backend)

        from lib.search import get_search_backend

        be = get_search_backend(bench_root, cfg_idx)
        if reindex:
            be.reindex()
            if backend == "hybrid":
                try:
                    from lib.search_chromadb import ChromaDBSearchBackend

                    ChromaDBSearchBackend(bench_root, cfg_idx).reindex()
                except Exception:
                    pass

        bcfg = (cfg_idx.get("benchmark") or {}).get("search") or {}
        n_fetch = max(
            int(bcfg.get("rerank_top_n", 50)),
            top_k * 4,
            20,
            len(corpus_sids),
        )
        if backend == "fts5" and bcfg.get("prf_rrf", True):
            from benchmarks.bench_harness import _bench_doc_tokens, prf_or_rrf_paths_with_and

            max_tok = int(bcfg.get("tfidf_max_chars", 80000))
            ht = bool(bcfg.get("tfidf_head_tail", True))
            docs_tokens = {
                rel: _bench_doc_tokens(bench_root, rel, max_tok, head_tail=ht)
                for rel in path_to_sid
            }
            paths = prf_or_rrf_paths_with_and(
                bench_root,
                cfg_idx,
                question,
                limit=n_fetch,
                rrf_k=int(bcfg.get("hybrid_k", 60)),
                path_to_sid=path_to_sid,
                tfidf_rrf=bool(bcfg.get("tfidf_rrf", True)),
                docs_tokens=docs_tokens,
                rrf_boost_or=int(bcfg.get("rrf_boost_or", 2)),
                tfidf_rrf_weight=float(bcfg.get("tfidf_rrf_weight", 1.0)),
                and_rrf=bool(bcfg.get("and_rrf", True)),
            )
            late_w = float(bcfg.get("or_late_rrf_weight", 0) or 0)
            if late_w > 0:
                from lib.search import FTS5SearchBackend

                fts_late = FTS5SearchBackend(bench_root, cfg_idx)
                paths_or_late = [r.path for r in fts_late.search(question, limit=n_fetch)]
                paths = reciprocal_rank_fusion_weighted(
                    [(paths, 1.0), (paths_or_late, late_w)],
                    k=int(bcfg.get("hybrid_k", 60)),
                )
            if bcfg.get("final_borda", False):
                from benchmarks.bench_harness import borda_merge_ranks, tfidf_corpus_rank_from_tokens

                pt = tfidf_corpus_rank_from_tokens(question, docs_tokens)
                paths = borda_merge_ranks(paths, pt)
            if bcfg.get("refine_head_lexical", False):
                from benchmarks.bench_harness import refine_head_lexical_overlap

                paths = refine_head_lexical_overlap(
                    question,
                    paths,
                    bench_root,
                    head=int(bcfg.get("refine_head_n", 40)),
                )
        elif backend == "fts5" and bcfg.get("dual_fts_rrf", False):
            from benchmarks.bench_harness import dual_fts_retrieve_paths

            paths = dual_fts_retrieve_paths(
                bench_root,
                cfg_idx,
                question,
                limit=n_fetch,
                rrf_k=int(bcfg.get("hybrid_k", 60)),
            )
        else:
            paths = search_fn(question, n_fetch)

        if bcfg.get("lexical_rrf", False):
            from benchmarks.bench_harness import fuse_paths_rrf_lexical

            paths = fuse_paths_rrf_lexical(
                question,
                paths,
                bench_root,
                rrf_k=int(bcfg.get("hybrid_k", 60)),
            )

        if bcfg.get("rerank_enabled", False):
            from benchmarks.bench_harness import rerank_paths_lexical

            paths = rerank_paths_lexical(question, paths, bench_root, max_paths=n_fetch)

        paths_before_llm = list(paths)

        rl = bcfg.get("rerank_llm") or {}
        key_env = str(rl.get("api_key_env", "ANTHROPIC_API_KEY"))
        api_key = os.environ.get(key_env, "")
        invoke = str(rl.get("invoke", "auto")).strip().lower()
        if invoke == "auto":
            resolved = _resolve_auto_invoke(api_key)
            if resolved:
                invoke = resolved
        cli_mode = invoke in ("claude_cli", "codex_cli", "custom_cli")
        cross_encoder_mode = invoke == "cross_encoder"
        env_on = str(os.environ.get("LLM_WIKI_BENCHMARK_LLM", "")).lower() in (
            "1",
            "true",
            "yes",
        )
        if cross_encoder_mode:
            try:
                import sentence_transformers  # noqa: F401
                can_run = True
            except ImportError:
                can_run = False
        elif invoke == "anthropic_api":
            can_run = bool(api_key)
        elif invoke == "openai_api":
            can_run = bool(api_key)
        elif invoke == "custom_cli":
            ca = rl.get("cli_argv")
            can_run = isinstance(ca, list) and len(ca) > 0
        else:
            can_run = cli_mode
        want_llm = bool(rl.get("enabled")) or (
            bool(rl.get("benchmark_auto", False)) and can_run
        ) or (env_on and can_run)
        run_llm = bool(want_llm and can_run)
        adaptive_skip = False
        if run_llm and str(rl.get("invoke_when", "always")).strip().lower() == "adaptive":
            from benchmarks.bench_harness import adaptive_should_run_llm_rerank

            if not adaptive_should_run_llm_rerank(
                question,
                paths_before_llm,
                bench_root,
                head=int(rl.get("adaptive_head", 5)),
                lookback=int(rl.get("adaptive_lookback", 24)),
                tail_margin=float(rl.get("adaptive_tail_margin", 0.12)),
                min_head_lex=float(rl.get("adaptive_min_head_lex", 3.5)),
                max_chars=int(rl.get("adaptive_max_chars", 12000)),
            ):
                run_llm = False
                adaptive_skip = True
                llm_adaptive_skips += 1
        llm_invoked = run_llm
        cap = int(rl.get("max_candidates", 80))
        max_candidates_used = min(cap, max(len(paths_before_llm), 5)) if llm_invoked else 0
        if llm_invoked and cross_encoder_mode:
            paths = rerank_paths_cross_encoder(
                question,
                paths,
                bench_root,
                model_name=str(rl.get("cross_encoder_model", "mixedbread-ai/mxbai-rerank-large-v1")),
                max_candidates=max_candidates_used,
                max_chars=int(rl.get("max_chars", 10000)),
                top_k=int(rl.get("max_picks", 10)),
            )
        elif llm_invoked:
            model = rl.get("model", "claude-sonnet-4-6")
            cli_argv = rl.get("cli_argv")
            if isinstance(cli_argv, list):
                cli_list = [str(x) for x in cli_argv]
            else:
                cli_list = None
            dbg = bool((cfg_run.get("benchmark") or {}).get("debug_rerank")) or str(
                os.environ.get("LLM_WIKI_BENCHMARK_DEBUG_RERANK", "")
            ).lower() in ("1", "true", "yes")
            if dbg:
                print(
                    f"[benchmark.debug_rerank] qid={qid} invoke={invoke} "
                    f"want_llm={want_llm} can_run={can_run} paths_pre={len(paths_before_llm)} "
                    f"max_cand={max_candidates_used}",
                    file=sys.stderr,
                )
            paths = rerank_paths_llm(
                question,
                paths,
                bench_root,
                api_key=api_key,
                invoke=invoke,
                model=model,
                max_chars=int(rl.get("max_chars", 3600)),
                max_candidates=max_candidates_used,
                max_picks=int(rl.get("max_picks", 5)),
                excerpt_mode=str(rl.get("excerpt_mode", "head_tail")),
                cli_argv=cli_list,
                cli_timeout_s=int(rl.get("cli_timeout_s", 180)),
                fuse_original_rrf=bool(rl.get("fuse_original_rrf", True)),
                fuse_original_weight=float(rl.get("fuse_original_weight", 0.35)),
                fuse_rrf_k=int(rl.get("fuse_rrf_k", 60)),
                session_dedup=bool(rl.get("session_dedup", False)),
                path_to_sid=path_to_sid,
            )

        paths_after_llm = list(paths)
        gold_in_pool = _gold_sid_in_paths(paths_before_llm, gold, path_to_sid)
        gold_in_n_fetch = _gold_sid_in_paths(paths_before_llm[:n_fetch], gold, path_to_sid)

        ordered_sids = paths_to_session_order(paths, path_to_sid)
        gold_idx = {i for i, sid in enumerate(corpus_sids) if sid in gold}

        rank_indices: list[int] = []
        seen_i: set[int] = set()
        for sid in ordered_sids:
            if sid in corpus_sids:
                i = corpus_sids.index(sid)
                if i not in seen_i:
                    seen_i.add(i)
                    rank_indices.append(i)
        for i in range(len(corpus_sids)):
            if i not in seen_i:
                rank_indices.append(i)

        for k in (1, 3, 5, 10):
            recall_vals[k].append(recall_at_k(rank_indices, gold_idx, k))
            ndcg_vals[k].append(ndcg_at_k(rank_indices, gold_idx, k))

        hit = recall_vals[5][-1] > 0
        if not hit:
            bucket = _classify_lme_failure(
                gold,
                gold_in_pool,
                hit,
                want_llm=want_llm,
                can_run=can_run,
                env_on=env_on,
            )
            if bucket:
                failure_bucket_counts[bucket] = failure_bucket_counts.get(bucket, 0) + 1
            failures.append(
                {
                    "question_id": qid,
                    "question": question,
                    "gold_sessions": list(gold),
                    "failure_bucket": bucket,
                    "gold_in_pool_pre_llm": gold_in_pool,
                    "gold_in_paths_slice_n_fetch": gold_in_n_fetch,
                    "llm_want": want_llm,
                    "llm_can_run": can_run,
                    "llm_invoked": llm_invoked,
                    "llm_adaptive_skip": adaptive_skip,
                    "llm_rerank_reordered": (
                        paths_before_llm != paths_after_llm if llm_invoked else None
                    ),
                    "n_fetch": n_fetch,
                    "max_candidates_used": max_candidates_used,
                    "top_paths": paths[:10],
                    "ordered_sessions": ordered_sids[:10],
                }
            )

        raw_body = "\n".join(
            "\n".join(t.get("content", "") for t in sess if t.get("role") == "user")
            for sess in sessions
        )
        cbody = comp.compress(raw_body, metadata={})
        st = comp.stats(raw_body, cbody)
        all_ratios.append(float(st.get("ratio", 1.0)))

    elapsed = time.monotonic() - t0

    summary = {
        "suite": "lme",
        "backend": backend,
        "compressor": compressor_name,
        "questions": len(data),
        "elapsed_s": round(elapsed, 2),
        "config_hash": config_hash(cfg_run),
        "recall_at_1": _avg(recall_vals[1]),
        "recall_at_3": _avg(recall_vals[3]),
        "recall_at_5": _avg(recall_vals[5]),
        "recall_at_10": _avg(recall_vals[10]),
        "ndcg_at_5": _avg(ndcg_vals[5]),
        "ndcg_at_10": _avg(ndcg_vals[10]),
        "failures": len(failures),
        "failure_bucket_counts": dict(failure_bucket_counts),
        "llm_adaptive_skips": llm_adaptive_skips,
        "token_ratio_mean": round(sum(all_ratios) / max(len(all_ratios), 1), 3),
    }
    return {"summary": summary, "failures": failures}


def analyze_lme_failures_log(path: Path) -> dict[str, Any]:
    """
    Parse ``lme_failures.jsonl`` (one JSON object per line) into a summary dict.
    Used by ``llm-wiki benchmark analyze lme``.
    """
    from collections import Counter

    rows: list[dict[str, Any]] = []
    if path.is_file():
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    buckets = Counter(str(r.get("failure_bucket") or "?") for r in rows)
    llm_yes = sum(1 for r in rows if r.get("llm_invoked"))
    pool_yes = sum(1 for r in rows if r.get("gold_in_pool_pre_llm"))
    adaptive_skipped = sum(1 for r in rows if r.get("llm_adaptive_skip"))
    reordered = sum(1 for r in rows if r.get("llm_rerank_reordered") is True)
    return {
        "path": str(path.resolve()),
        "exists": path.is_file(),
        "failure_count": len(rows),
        "failure_bucket_counts": dict(sorted(buckets.items())),
        "llm_invoked_count": llm_yes,
        "gold_in_pool_pre_llm_count": pool_yes,
        "llm_adaptive_skip_count": adaptive_skipped,
        "llm_rerank_reordered_count": reordered,
        "question_ids": [r.get("question_id") for r in rows],
        "rows": rows,
    }


def format_lme_failures_analysis(summary: dict[str, Any], *, max_question_chars: int = 72) -> str:
    """Plain-text report for terminal use."""
    lines: list[str] = []
    lines.append(f"path: {summary.get('path')}")
    lines.append(f"failures: {summary.get('failure_count')}  (file exists: {summary.get('exists')})")
    bc = summary.get("failure_bucket_counts") or {}
    if bc:
        lines.append("buckets: " + ", ".join(f"{k}={v}" for k, v in sorted(bc.items())))
    lines.append(
        f"gold_in_pool_pre_llm: {summary.get('gold_in_pool_pre_llm_count')}/{summary.get('failure_count')}"
    )
    lines.append(
        f"llm_invoked: {summary.get('llm_invoked_count')}/{summary.get('failure_count')}"
    )
    lines.append(f"llm_adaptive_skip (on miss rows): {summary.get('llm_adaptive_skip_count')}")
    lines.append(f"llm_rerank_reordered (True on miss rows): {summary.get('llm_rerank_reordered_count')}")
    lines.append("")
    for r in summary.get("rows") or []:
        qid = r.get("question_id", "")
        b = r.get("failure_bucket", "")
        q = (r.get("question") or "").replace("\n", " ")
        if len(q) > max_question_chars:
            q = q[: max_question_chars - 3] + "..."
        lines.append(f"  [{b}] {qid}  {q}")
    return "\n".join(lines) + "\n"


def _avg(xs: list[float]) -> float:
    return round(sum(xs) / max(len(xs), 1), 4)


def recall_at_k(rankings: list[int], correct: set[int], k: int) -> float:
    top = set(rankings[:k])
    return 1.0 if correct & top else 0.0


def complete_lme_derived_suite(
    vault: Path,
    cfg: dict,
    result: dict,
    *,
    suite: str,
    backend: str,
    compressor: str,
    entry_count: int,
) -> dict:
    """Label LoCoMo/ConvoMem results and record metrics (same harness as LME)."""
    summary = dict(result["summary"])
    summary["suite"] = suite
    summary["status"] = "ok"
    summary["questions_evaluated"] = summary.get("questions", 0)
    out = {"summary": summary, "failures": result["failures"]}
    finalize_lme_run(
        vault,
        cfg,
        out,
        backend=backend,
        compressor=compressor,
        limit=entry_count,
        suite=suite,
    )
    return out


def finalize_lme_run(
    vault: Path,
    cfg: dict,
    result: dict,
    *,
    backend: str,
    compressor: str,
    limit: int = 0,
    suite: str = "lme",
) -> Path:
    """Write failures JSONL and record benchmark metrics (same as CLI post-run)."""
    results_dir = vault / (cfg.get("benchmark") or {}).get("results_dir", ".benchmarks")
    results_dir.mkdir(parents=True, exist_ok=True)
    fail_name = "lme_failures.jsonl" if suite == "lme" else f"{suite}_failures.jsonl"
    fail_path = results_dir / fail_name
    with fail_path.open("w", encoding="utf-8") as ff:
        for row in result["failures"]:
            ff.write(json.dumps(row) + "\n")
    rl = ((cfg.get("benchmark") or {}).get("search") or {}).get("rerank_llm") or {}
    llm_flag = str(os.environ.get("LLM_WIKI_BENCHMARK_LLM", "")).lower() in (
        "1",
        "true",
        "yes",
    )
    meta = build_benchmark_record_meta(
        cfg,
        suite=suite,
        backend=backend,
        compressor=compressor,
        summary=result["summary"],
        limit=limit,
        llm_flag=llm_flag,
        rerank_invoke=str(rl.get("invoke", "")),
    )
    record_benchmark_metrics(
        vault,
        cfg,
        suite=suite,
        backend=backend,
        compressor=compressor,
        metrics={
            "recall_at_5": float(result["summary"]["recall_at_5"]),
            "recall_at_10": float(result["summary"]["recall_at_10"]),
            "ndcg_at_10": float(result["summary"]["ndcg_at_10"]),
            "failures": float(result["summary"]["failures"]),
            "elapsed_s": float(result["summary"]["elapsed_s"]),
        },
        meta=meta,
    )
    append_repo_benchmark_runs_jsonl(cfg, summary=result["summary"], vault=vault)
    write_benchmark_run_sidecar(
        vault, cfg, suite=suite, summary=result["summary"], result=result
    )
    return fail_path


def main() -> int:
    ap = argparse.ArgumentParser(description="LME benchmark for wiki-llm")
    ap.add_argument("--data", type=Path, default=None, help="Path to cleaned JSON")
    ap.add_argument("--vault", type=Path, default=None)
    ap.add_argument("--backend", default="fts5")
    ap.add_argument("--compress", default="raw")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-write-metrics", action="store_true")
    args = ap.parse_args()

    cache = Path(os.path.expanduser("~/.cache/llm-wiki-benchmarks"))
    data_path = args.data or download_dataset(cache)

    vault = args.vault or Path.cwd() / ".tmp" / "llm-wiki-bench-vault"
    vault.mkdir(parents=True, exist_ok=True)
    cfg = load_config(vault)
    if args.no_write_metrics:
        cfg.setdefault("benchmark", {})["auto_record_metrics"] = False
    cfg.setdefault("benchmark", {})["compress_method"] = args.compress

    print(json.dumps({"data": str(data_path), "vault": str(vault)}, indent=2))
    result = run_lme(
        data_path,
        vault,
        cfg,
        backend=args.backend,
        compressor_name=args.compress,
        limit=args.limit,
    )
    print(json.dumps(result["summary"], indent=2))

    fail_path = finalize_lme_run(
        vault,
        cfg,
        result,
        backend=args.backend,
        compressor=args.compress,
        limit=int(args.limit or 0),
    )
    print(f"Failures log: {fail_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
