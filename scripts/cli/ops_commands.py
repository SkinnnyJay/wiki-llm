"""Knowledge graph, session memory, metrics, benchmarks, interactive configure."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.config_loader import DEFAULTS, load_config, save_config
from lib.paths import plugin_root, resolve_vault

# ── Knowledge graph CLI ──────────────────────────────────────────────────────

def cmd_kg(args: argparse.Namespace) -> int:
    from lib.knowledge_graph import get_kg_backend
    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    kg = get_kg_backend(vault, cfg)
    sub = getattr(args, "kg_sub", None)

    if sub == "add":
        tid = kg.add_triple(
            args.subject, args.predicate, args.object,
            valid_from=getattr(args, "valid_from", None) or None,
            source=getattr(args, "source", None) or None,
        )
        print(f"Added: {args.subject} → {args.predicate} → {args.object}  (id: {tid})")
        return 0

    if sub == "query":
        results = kg.query_entity(args.entity, as_of=getattr(args, "as_of", None) or None)
        if getattr(args, "json_out", False):
            from lib.emit import emit_json

            emit_json({"entity": args.entity, "facts": results, "count": len(results)})
            return 0
        if not results:
            print(f"No facts found for: {args.entity}")
            return 0
        for t in results:
            ended = f"  (ended {t['valid_until']})" if t.get("valid_until") else ""
            print(f"  {t['s']} → {t['p']} → {t['o']}  [{t.get('valid_from', '?')}]{ended}")
        return 0

    if sub == "invalidate":
        ok = kg.invalidate(
            args.subject, args.predicate, args.object,
            ended=getattr(args, "ended", None) or None,
        )
        if ok:
            print(f"Invalidated: {args.subject} → {args.predicate} → {args.object}")
        else:
            print("No matching active triple found.", file=sys.stderr)
        return 1 if not ok else 0

    if sub == "timeline":
        entity = getattr(args, "entity", None) or None
        results = kg.timeline(entity)
        if not results:
            print("No facts." if not entity else f"No facts for: {entity}")
            return 0
        for t in results:
            ended = f" → ended {t['valid_until']}" if t.get("valid_until") else ""
            print(f"  [{t.get('valid_from', '?')}] {t['s']} → {t['p']} → {t['o']}{ended}")
        return 0

    if sub == "stats":
        s = kg.stats()
        if getattr(args, "json_out", False):
            from lib.emit import emit_json

            emit_json(s)
            return 0
        for k, v in s.items():
            print(f"  {k}: {v}")
        return 0

    if sub == "rebuild":
        from lib.knowledge_graph import rebuild_knowledge_graph

        result = rebuild_knowledge_graph(vault, cfg, backend=kg)
        if result.get("disabled"):
            print("Knowledge graph is disabled in config.json.", file=sys.stderr)
            return 1
        print(f"Rebuilt: {result.get('added', 0)} triples added, {result.get('total_triples', 0)} total, {result.get('entities', 0)} entities")
        return 0

    print("Usage: llm-wiki kg {add|query|invalidate|timeline|stats|rebuild}", file=sys.stderr)
    return 1


def _resolve_message_preview_for_log(args: argparse.Namespace) -> tuple[str | None, int | None]:
    """Return (preview, exit_code). exit_code is set on fatal read errors.

    Prefer ``--message-preview-file`` so hooks avoid shell-quoting issues with
    quotes, newlines, or box-drawing characters in assistant messages.
    """
    fp = getattr(args, "message_preview_file", None)
    if fp:
        p = Path(fp).expanduser()
        if not p.is_file():
            print(f"memory log: not a file: {fp}", file=sys.stderr)
            return None, 1
        try:
            raw = p.read_bytes()
        except OSError as e:
            print(f"memory log: {e}", file=sys.stderr)
            return None, 1
        max_b = 4 * 1024 * 1024
        if len(raw) > max_b:
            print("memory log: preview file exceeds 4 MiB — refusing", file=sys.stderr)
            return None, 1
        return raw.decode("utf-8", errors="replace"), None
    inline = getattr(args, "message_preview", None)
    if inline is not None:
        return inline, None
    return os.environ.get("LLM_WIKI_MESSAGE_PREVIEW"), None


def cmd_memory(args: argparse.Namespace) -> int:
    from lib import session_memory as mem

    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    sub = getattr(args, "memory_sub", None)

    def _sid() -> str:
        return mem.resolve_session_arg(
            vault,
            session_id=getattr(args, "session_id", None),
            current=getattr(args, "current", False),
        )

    if sub == "save":
        if not mem.memory_enabled(cfg):
            print("memory.enabled is false — skipping.", file=sys.stderr)
            return 0
        if not getattr(args, "current", False) and not getattr(args, "session_id", None):
            print("memory save: pass --session-id or --current", file=sys.stderr)
            return 1
        try:
            sid = _sid()
        except (ValueError, FileNotFoundError) as e:
            print(str(e), file=sys.stderr)
            return 1
        tags = None
        raw_tags = getattr(args, "tags", None) or ""
        if raw_tags.strip():
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        meta = None
        if getattr(args, "metadata", None):
            try:
                meta = json.loads(args.metadata)
            except json.JSONDecodeError:
                print("Invalid JSON for --metadata", file=sys.stderr)
                return 1
        path = mem.memory_save(
            vault,
            cfg,
            sid,
            summary=getattr(args, "summary", None),
            compact_summary=getattr(args, "compact_summary", None),
            tags=tags,
            metadata=meta,
        )
        print(path.relative_to(vault))
        return 0

    if sub == "log":
        if not mem.memory_enabled(cfg):
            print("memory.enabled is false — skipping.", file=sys.stderr)
            return 0
        if not getattr(args, "current", False) and not getattr(args, "session_id", None):
            print("memory log: pass --session-id or --current", file=sys.stderr)
            return 1
        try:
            sid = _sid()
        except (ValueError, FileNotFoundError) as e:
            print(str(e), file=sys.stderr)
            return 1
        preview, err = _resolve_message_preview_for_log(args)
        if err is not None:
            return err
        path = mem.memory_log_round(
            vault,
            cfg,
            sid,
            message_preview=preview,
        )
        print(path.relative_to(vault))
        return 0

    if sub == "list":
        rows = mem.memory_list(
            vault,
            cfg,
            session_id=getattr(args, "session_filter", None),
            tag=getattr(args, "tag", None),
        )
        if getattr(args, "json_out", False):
            print(json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(
                    f"{r['session_id']}\t{r.get('updated', '')}\trounds={r.get('rounds', 0)}\t"
                    f"tags={','.join(r.get('tags', []))}"
                )
        return 0

    if sub == "show":
        sid = getattr(args, "session_id_arg", None)
        if getattr(args, "current", False):
            try:
                sid = mem.resolve_current_session(vault)
            except (ValueError, FileNotFoundError) as e:
                print(str(e), file=sys.stderr)
                return 1
        elif not sid:
            print("show: pass SESSION_ID or --current", file=sys.stderr)
            return 1
        text = mem.memory_show(vault, cfg, sid)
        if getattr(args, "json_out", False):
            from lib.emit import emit_json

            emit_json({"session_id": sid, "content": text})
            return 0
        print(text, end="" if text.endswith("\n") else "\n")
        return 0

    if sub == "recall":
        q = (getattr(args, "query", None) or "").strip()
        if not q:
            print("recall: query required", file=sys.stderr)
            return 1
        sf = getattr(args, "session_filter", None)
        if getattr(args, "current", False):
            try:
                sf = mem.resolve_current_session(vault)
            except (ValueError, FileNotFoundError) as e:
                print(str(e), file=sys.stderr)
                return 1
        results = mem.memory_recall(
            vault,
            cfg,
            q,
            session_id=sf,
            tag=getattr(args, "tag", None),
            limit=getattr(args, "limit", 5),
        )
        if getattr(args, "json_out", False):
            from lib.emit import emit_json

            emit_json({"results": [r.to_dict() for r in results], "count": len(results)})
            return 0
        for r in results:
            print(f"{r.path}\t{r.score}\t{r.snippet[:200]}")
        return 0

    if sub == "prune":
        if not mem.memory_enabled(cfg):
            print("memory.enabled is false — skipping.", file=sys.stderr)
            return 0
        try:
            out = mem.memory_prune(
                vault,
                cfg,
                session_id=getattr(args, "session_filter", None),
                tag=getattr(args, "tag", None),
                older_than_days=getattr(args, "older_than", None),
                keep=getattr(args, "keep", None),
                dry_run=getattr(args, "dry_run", False),
            )
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 1
        for d in out["deleted"]:
            print("deleted" if not out["dry_run"] else "would delete", d)
        return 0

    print("Usage: llm-wiki memory {save|log|list|show|recall|prune}", file=sys.stderr)
    return 1


def cmd_metrics(args: argparse.Namespace) -> int:
    from lib.metrics import MetricsRecorder
    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    cfg.setdefault("metrics", {})["enabled"] = True
    m = MetricsRecorder(vault, cfg)
    sub = getattr(args, "metrics_sub", None)

    if sub == "record":
        value: float | int | str = args.value
        try:
            value = int(args.value)
        except ValueError:
            try:
                value = float(args.value)
            except ValueError:
                pass
        meta = None
        if getattr(args, "meta", None):
            try:
                meta = json.loads(args.meta)
            except json.JSONDecodeError:
                print(f"Invalid JSON for --meta: {args.meta}", file=sys.stderr)
                return 1
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if getattr(args, "tags", "") else None
        m.record(args.key, value, meta=meta, tags=tags)
        print(f"Recorded: {args.key}={value}")
        return 0

    if sub == "query":
        records = m.query(
            key=getattr(args, "key", None),
            since=getattr(args, "since", None),
            limit=getattr(args, "limit", 100),
        )
        if not records:
            print("No records found.")
            return 0
        if getattr(args, "metrics_json", False):
            print(json.dumps(records, indent=2))
        else:
            for rec in records:
                ts = rec.get("ts", "?")[:19]
                k = rec.get("key", "?")
                v = rec.get("value", "?")
                meta = rec.get("meta", {})
                meta_str = f"  {meta}" if meta else ""
                print(f"  {ts}  {k}={v}{meta_str}")
        return 0

    if sub == "stats":
        s = m.stats()
        for k, v in s.items():
            print(f"  {k}: {v}")
        return 0

    if sub == "clear":
        if not getattr(args, "yes", False):
            print("Use --yes to confirm clearing metrics.", file=sys.stderr)
            return 1
        result = m.clear(before=getattr(args, "before", None))
        print(f"Removed {result['removed']} records.")
        return 0

    if sub == "report":
        from lib.metrics_report import build_metrics_report

        out_arg = getattr(args, "metrics_report_out", None)
        out_dir = (
            Path(out_arg).resolve()
            if out_arg
            else (Path.cwd() / ".tmp" / "llm-wiki-metrics").resolve()
        )
        try:
            path = build_metrics_report(
                vault,
                cfg,
                out_dir,
                since=getattr(args, "metrics_report_since", None),
                key=getattr(args, "metrics_report_key", None),
            )
        except FileNotFoundError as e:
            print(e, file=sys.stderr)
            return 1
        print(f"Metrics dashboard → {path}")
        print(f"  cd {path.parent} && python3 -m http.server 8890")
        return 0

    if sub == "summary":
        from lib.metrics_report import build_metrics_summary

        if getattr(args, "metrics_summary_json", False):
            out = build_metrics_summary(
                vault,
                cfg,
                since=getattr(args, "metrics_summary_since", None),
                key=getattr(args, "metrics_summary_key", None),
                as_json=True,
            )
            assert isinstance(out, dict)
            print(json.dumps(out, indent=2))
        else:
            text = build_metrics_summary(
                vault,
                cfg,
                since=getattr(args, "metrics_summary_since", None),
                key=getattr(args, "metrics_summary_key", None),
                as_json=False,
            )
            assert isinstance(text, str)
            print(text)
        return 0

    print("Usage: llm-wiki metrics {record|query|stats|clear|report|summary}", file=sys.stderr)
    return 1


def cmd_benchmark(args: argparse.Namespace) -> int:
    """Run retrieval benchmarks (LME, LoCoMo, ConvoMem) and print metrics."""
    from lib.paths import plugin_root

    root = plugin_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    bcfg = cfg.get("benchmark") or {}
    sub = getattr(args, "benchmark_sub", None)
    if not bcfg.get("enabled", True) and sub not in ("analyze", "suites"):
        print("benchmark.enabled is false in config.json", file=sys.stderr)
        return 1

    if sub == "suites":
        from benchmarks.suite_help import describe_benchmark_suites

        print(describe_benchmark_suites(), end="")
        return 0

    if sub == "run":
        raw_suite = getattr(args, "benchmark_suite", None) or "lme"
        suite = "lme" if raw_suite in ("lme", "longmemeval") else raw_suite
        no_metrics = getattr(args, "benchmark_no_metrics", False)
        if no_metrics:
            cfg.setdefault("benchmark", {})["auto_record_metrics"] = False
        compress_arg = getattr(args, "benchmark_compress", None)
        compress = compress_arg if compress_arg is not None else bcfg.get("compress_method", "raw")
        backend_arg = getattr(args, "benchmark_backend", None)
        backend = backend_arg if backend_arg is not None else (bcfg.get("search") or {}).get("backend", "fts5")
        limit = int(getattr(args, "benchmark_limit", 0) or 0)
        data_arg = getattr(args, "benchmark_data", None)
        top_k = int(getattr(args, "benchmark_top_k", 5) or 5)

        backends = (
            ["fts5", "grep", "chromadb", "hybrid"]
            if str(backend).lower() == "all"
            else [str(backend).lower()]
        )
        compressors = (
            ["raw", "steno", "prune", "extract", "compact"]
            if str(compress).lower() == "all"
            else [str(compress).lower()]
        )

        if suite == "lme":
            from benchmarks.lme_bench import download_dataset, finalize_lme_run, run_lme

            cache = Path(os.path.expanduser(bcfg.get("data_cache_dir", "~/.cache/llm-wiki-benchmarks")))
            data_path = Path(data_arg).resolve() if data_arg else download_dataset(cache)

            peer_list = getattr(args, "benchmark_peer", None) or []
            strict_peers = bool(getattr(args, "benchmark_strict_peers", False)) or bool(
                (bcfg.get("peers") or {}).get("strict", False)
            )
            if peer_list:
                from benchmarks.peer_lme import run_lme_peers

                cfg_run = load_config(vault)
                if no_metrics:
                    cfg_run.setdefault("benchmark", {})["auto_record_metrics"] = False
                try:
                    out = run_lme_peers(
                        data_path,
                        vault,
                        cfg_run,
                        peer_ids=list(peer_list),
                        limit=limit,
                        top_k=top_k,
                        strict_peers=strict_peers,
                    )
                except RuntimeError as e:
                    print(str(e), file=sys.stderr)
                    return 1
                print(json.dumps(out, indent=2, default=str))
                return 0

            last_fail: Path | None = None
            for be in backends:
                for comp in compressors:
                    cfg_run = load_config(vault)
                    if no_metrics:
                        cfg_run.setdefault("benchmark", {})["auto_record_metrics"] = False
                    cfg_run.setdefault("benchmark", {})["compress_method"] = comp
                    result = run_lme(
                        data_path,
                        vault,
                        cfg_run,
                        backend=be,
                        compressor_name=comp,
                        limit=limit,
                        top_k=top_k,
                    )
                    print(json.dumps(result["summary"], indent=2))
                    last_fail = finalize_lme_run(
                        vault,
                        cfg_run,
                        result,
                        backend=be,
                        compressor=comp,
                        limit=limit,
                    )
            if last_fail is not None:
                print(f"Failures log (last run): {last_fail}", file=sys.stderr)
            return 0
        if suite in ("locomo", "convomem"):
            if suite == "locomo":
                from benchmarks.locomo_bench import run_locomo as run_peer
            else:
                from benchmarks.convomem_bench import run_convomem as run_peer

            data_path = Path(data_arg).resolve() if data_arg else None
            out = run_peer(vault, cfg, limit=limit, data_path=data_path)
            print(json.dumps(out.get("summary", out), indent=2))
            return 0

        print(f"Unknown benchmark suite: {suite}", file=sys.stderr)
        return 1

    if sub == "report":
        from lib.metrics_report import load_metrics_records

        since = getattr(args, "benchmark_since", None)
        records = load_metrics_records(vault, cfg, since=since, limit=0)
        bench = [r for r in records if str(r.get("key", "")).startswith("benchmark.")]
        if getattr(args, "benchmark_json", False):
            print(json.dumps(bench[-2000:], indent=2))
            return 0
        for r in bench[-50:]:
            print(f"{r.get('ts', '')[:19]}  {r.get('key')}={r.get('value')}  {r.get('meta', {})}")
        return 0

    if sub == "history":
        from lib.metrics_report import load_metrics_records

        hist_limit = int(getattr(args, "benchmark_history_limit", 30))
        records = load_metrics_records(vault, cfg, limit=0)
        bench = [r for r in records if str(r.get("key", "")).startswith("benchmark.")]
        bench = bench[-hist_limit:]
        for r in bench:
            print(f"{r.get('ts', '')[:19]}  {r.get('key')}={r.get('value')}")
        return 0

    if sub == "compare":
        from lib.metrics_report import iter_benchmark_lme_snapshots

        rows = iter_benchmark_lme_snapshots(vault, cfg, limit=500)
        if len(rows) < 2:
            print(
                "Need at least two benchmark.lme.recall_at_5 records in metrics JSONL.",
                file=sys.stderr,
            )
            return 1
        ia = int(getattr(args, "benchmark_compare_a", -2))
        ib = int(getattr(args, "benchmark_compare_b", -1))
        ra = rows[ia]
        rb = rows[ib]
        out = {
            "a": {
                "ts": ra.get("ts"),
                "recall_at_5": ra.get("value"),
                "meta": ra.get("meta"),
            },
            "b": {
                "ts": rb.get("ts"),
                "recall_at_5": rb.get("value"),
                "meta": rb.get("meta"),
            },
        }
        print(json.dumps(out, indent=2, default=str))
        return 0

    if sub == "analyze":
        from benchmarks.lme_bench import analyze_lme_failures_log, format_lme_failures_analysis

        suite = getattr(args, "benchmark_analyze_suite", "lme") or "lme"
        if suite != "lme":
            print("benchmark analyze: only --suite lme is supported", file=sys.stderr)
            return 1
        raw_path = getattr(args, "benchmark_failures_path", None)
        if raw_path:
            fail_path = Path(str(raw_path)).resolve()
        else:
            results_dir = vault / str(bcfg.get("results_dir") or ".benchmarks")
            fail_path = results_dir / "lme_failures.jsonl"
        summary = analyze_lme_failures_log(fail_path)
        if getattr(args, "benchmark_analyze_json", False):
            print(json.dumps(summary, indent=2, default=str))
        else:
            print(format_lme_failures_analysis(summary), end="")
        return 0

    print(
        "Usage: llm-wiki benchmark {run|suites|report|history|compare|analyze}",
        file=sys.stderr,
    )
    return 1


def cmd_interactive_configure() -> int:
    vault = resolve_vault()
    cfg = load_config(vault)
    print("llm-wiki configure (interactive) — enter empty to keep current")
    print("Vault:", vault)
    print()

    og = input(f"viewer.og_base_url [{cfg.get('viewer', {}).get('og_base_url', '')}]: ").strip()
    if og:
        cfg.setdefault("viewer", {})["og_base_url"] = og
    cur_name = (cfg.get("persona") or {}).get("name") or DEFAULTS.get("persona", {}).get("name", "Gennie")
    pn = input(f"persona.name (wiki display name) [{cur_name}]: ").strip()
    if pn:
        cfg.setdefault("persona", {})["name"] = pn

    print()
    print("─── Feature toggles ───")
    for key, label, reason in [
        ("viewer", "Static viewer", "browse wiki in a local web page"),
        ("git", "Vault git", "track changes, undo mistakes"),
        ("research_loop", "Research loop", "batch web research from task lists"),
        ("ingestion_security", "Ingestion security", "scan ingested content for threats"),
    ]:
        cur = cfg.get(key, {}).get("enabled", DEFAULTS.get(key, {}).get("enabled"))
        v = input(f"  {label} — {reason} (y/n) [{'y' if cur else 'n'}]: ").strip().lower()
        if v in ("y", "n"):
            cfg.setdefault(key, {})["enabled"] = v == "y"

    print()
    print("─── MCP server ───")
    mcp_cur = (cfg.get("mcp") or {}).get("enabled", True)
    v = input(f"  MCP server — agents query wiki via 33 tools (y/n) [{'y' if mcp_cur else 'n'}]: ").strip().lower()
    if v in ("y", "n"):
        cfg.setdefault("mcp", {})["enabled"] = v == "y"

    sb_cur = (cfg.get("mcp") or {}).get("search_backend", "fts5")
    print(f"  Search backend: fts5 (ranked) | grep (simple) | chromadb (semantic) | hybrid (FTS+Chroma RRF)")
    sb = input(f"  Search backend [{sb_cur}]: ").strip().lower()
    if sb in ("fts5", "grep", "chromadb", "hybrid"):
        cfg.setdefault("mcp", {})["search_backend"] = sb

    print()
    print("─── Knowledge graph ───")
    kg_cur = (cfg.get("knowledge_graph") or {}).get("enabled", True)
    v = input(f"  Knowledge graph — entity relationships from wiki (y/n) [{'y' if kg_cur else 'n'}]: ").strip().lower()
    if v in ("y", "n"):
        cfg.setdefault("knowledge_graph", {})["enabled"] = v == "y"

    kb_cur = (cfg.get("knowledge_graph") or {}).get("backend", "json")
    print(f"  KG backend: json (simple file) | sqlite (temporal queries)")
    kb = input(f"  KG backend [{kb_cur}]: ").strip().lower()
    if kb in ("json", "sqlite"):
        cfg.setdefault("knowledge_graph", {})["backend"] = kb

    save_config(vault, cfg)
    print("\nSaved.")
    return 0

