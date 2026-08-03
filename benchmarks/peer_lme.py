"""LongMemEval-style runs against optional peer memory backends (mem0, shell bridges, …)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from lib.config_loader import deep_merge
from lib.metrics import MetricsRecorder

from benchmarks.bench_harness import build_benchmark_record_meta, config_hash, ndcg_at_k
from benchmarks.lme_bench import _load_lme_data
from benchmarks.peers import (
    dimensions_to_jsonable,
    get_peer_adapter,
    merge_dimension_scores,
)
from benchmarks.peers.mem0_adapter import Mem0PeerAdapter
from benchmarks.peers.registry import default_peer_cache_root


def _avg(xs: list[float]) -> float:
    return round(sum(xs) / max(len(xs), 1), 4)


def recall_at_k_rankings(rankings: list[int], correct_indices: set[int], k: int) -> float:
    top = set(rankings[:k])
    return 1.0 if correct_indices & top else 0.0


def run_lme_peers(
    data_path: Path | list[dict],
    vault: Path,
    cfg: dict,
    *,
    peer_ids: list[str],
    limit: int = 0,
    top_k: int = 5,
    strict_peers: bool = False,
) -> dict[str, Any]:
    """
    Run LME against each peer id. Skipped peers still emit dimensions (editorial/proxy).

    Returns ``{"suite": "lme_peers", "peers": { peer_id: {...} }}``.
    """
    data = _load_lme_data(data_path)
    if limit > 0:
        data = data[:limit]

    cfg_run = deep_merge(cfg, {})
    out: dict[str, Any] = {
        "suite": "lme_peers",
        "questions": len(data),
        "config_hash": config_hash(cfg_run),
        "peers": {},
    }

    for raw_pid in peer_ids:
        peer_id = str(raw_pid).strip().lower().replace("_", "-")
        adapter = get_peer_adapter(peer_id, cfg=cfg_run)
        h = adapter.health()
        cap = adapter.capabilities()

        if not h.ok:
            ds = merge_dimension_scores(
                peer_id,
                cap,
                heavy_deps=False,
                roundtrip_ok=None,
                recall_ran=False,
            )
            out["peers"][peer_id] = {
                "skipped": True,
                "health": {"ok": False, "reason": h.reason, "detail": h.detail},
                "dimensions": dimensions_to_jsonable(ds),
                "summary": None,
            }
            if strict_peers:
                raise RuntimeError(f"peer {peer_id} unavailable (strict): {h.reason}")
            continue

        recall_vals = {k: [] for k in (1, 3, 5, 10)}
        ndcg_vals = {k: [] for k in (1, 3, 5, 10)}
        failures: list[dict[str, Any]] = []
        roundtrip_last: bool | None = None

        t0 = time.monotonic()
        try:
            for idx, entry in enumerate(data):
                sessions = entry["haystack_sessions"]
                session_ids = entry["haystack_session_ids"]
                dates = entry["haystack_dates"]
                question = entry["question"]
                gold = set(entry["answer_session_ids"])
                qid = entry.get("question_id", str(idx))
                corpus_sids = list(session_ids)
                gold_idx = {i for i, sid in enumerate(corpus_sids) if sid in gold}

                n_fetch = max(top_k * 4, 20, len(corpus_sids))
                run_cache = default_peer_cache_root(cfg_run) / peer_id / f"q_{idx:05d}"
                run_cache.mkdir(parents=True, exist_ok=True)

                ordered_sids = adapter.ingest_and_query(
                    sessions=sessions,
                    session_ids=session_ids,
                    dates=dates,
                    question=question,
                    n_fetch=n_fetch,
                    run_idx=idx,
                    run_cache=run_cache,
                )

                if isinstance(adapter, Mem0PeerAdapter):
                    roundtrip_last = adapter.last_roundtrip_ok()

                seen_i: set[int] = set()
                rank_indices: list[int] = []
                for sid in ordered_sids:
                    if sid in corpus_sids:
                        i = corpus_sids.index(sid)
                        if i not in seen_i:
                            seen_i.add(i)
                            rank_indices.append(i)
                for i in range(len(corpus_sids)):
                    if i not in seen_i:
                        rank_indices.append(i)

                for kk in (1, 3, 5, 10):
                    recall_vals[kk].append(
                        recall_at_k_rankings(rank_indices, gold_idx, kk)
                    )
                    ndcg_vals[kk].append(ndcg_at_k(rank_indices, gold_idx, kk))

                hit = recall_vals[5][-1] > 0
                if not hit:
                    failures.append(
                        {
                            "question_id": qid,
                            "question": question,
                            "gold_sessions": list(gold),
                            "ordered_sessions": ordered_sids[:10],
                        }
                    )
        except Exception as e:
            out["peers"][peer_id] = {
                "skipped": True,
                "error": str(e),
                "health": {"ok": False, "reason": "runtime_error", "detail": str(e)},
                "dimensions": dimensions_to_jsonable(
                    merge_dimension_scores(
                        peer_id,
                        cap,
                        heavy_deps=peer_id == "mem0",
                        roundtrip_ok=roundtrip_last,
                        recall_ran=False,
                    )
                ),
                "summary": None,
            }
            if strict_peers:
                raise
            continue

        elapsed = time.monotonic() - t0
        heavy = peer_id == "mem0"
        ds = merge_dimension_scores(
            peer_id,
            cap,
            heavy_deps=heavy,
            roundtrip_ok=roundtrip_last,
            recall_ran=True,
        )

        summary = {
            "suite": "lme_peer",
            "peer": peer_id,
            "backend": f"peer:{peer_id}",
            "compressor": "raw",
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
        }

        out["peers"][peer_id] = {
            "skipped": False,
            "health": {"ok": True, "reason": "", "detail": ""},
            "dimensions": dimensions_to_jsonable(ds),
            "summary": summary,
            "failures": failures,
        }

        finalize_peer_lme_run(
            vault,
            cfg_run,
            peer_id=peer_id,
            summary=summary,
            dimensions=ds,
            failures=failures,
            limit=limit,
        )

    return out


def finalize_peer_lme_run(
    vault: Path,
    cfg: dict,
    *,
    peer_id: str,
    summary: dict[str, Any],
    dimensions: Any,
    failures: list[dict[str, Any]],
    limit: int,
) -> Path:
    """Write failures JSONL and append ``benchmark.peer.<id>.*`` metrics."""
    results_dir = vault / (cfg.get("benchmark") or {}).get("results_dir", ".benchmarks")
    results_dir.mkdir(parents=True, exist_ok=True)
    safe = peer_id.replace("/", "_").replace(".", "_")
    fail_path = results_dir / f"peer_{safe}_failures.jsonl"
    with fail_path.open("w", encoding="utf-8") as ff:
        for row in failures:
            ff.write(json.dumps(row) + "\n")

    bcfg = cfg.get("benchmark") or {}
    if not bcfg.get("auto_record_metrics", True):
        return fail_path

    cfg_m = deep_merge(cfg, {"metrics": {"enabled": True}})
    m = MetricsRecorder(vault, cfg_m)
    if not m.enabled:
        return fail_path

    meta = build_benchmark_record_meta(
        cfg,
        suite=f"peer.{peer_id}",
        backend="peer",
        compressor="raw",
        summary=summary,
        limit=limit,
        llm_flag=False,
        rerank_invoke="",
    )
    meta["peer"] = peer_id

    prefix = f"benchmark.peer.{peer_id}"
    m.record(f"{prefix}.recall_at_5", float(summary["recall_at_5"]), meta=meta, tags=["peer", peer_id])
    m.record(f"{prefix}.failures", float(summary["failures"]), meta=meta, tags=["peer", peer_id])
    m.record(f"{prefix}.elapsed_s", float(summary["elapsed_s"]), meta=meta, tags=["peer", peer_id])

    d = dimensions
    for key in ("data_integrity", "simplicity", "integration", "arch_maturity"):
        val = getattr(d, key, None)
        if val is not None:
            m.record(f"{prefix}.dimensions.{key}", float(val), meta=meta, tags=["peer", peer_id])
    ov = d.overall()
    if ov is not None:
        m.record(f"{prefix}.dimensions.overall", float(ov), meta=meta, tags=["peer", peer_id])

    from benchmarks.bench_harness import append_repo_benchmark_runs_jsonl

    append_repo_benchmark_runs_jsonl(cfg, summary=summary, vault=vault)
    return fail_path
