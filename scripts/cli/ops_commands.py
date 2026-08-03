"""Knowledge graph, session memory, metrics, benchmarks, interactive configure."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import cast

SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.config_loader import DEFAULTS, load_config, save_config
from lib.paths import plugin_root, resolve_vault

from cli.arguments import (
    BenchmarkArgs,
    KnowledgeGraphArgs,
    MemoryArgs,
    MetricsArgs,
    required_text,
)

# ── Knowledge graph CLI ──────────────────────────────────────────────────────

def cmd_kg(args: argparse.Namespace) -> int:
    from lib.knowledge_graph import get_kg_backend

    options = KnowledgeGraphArgs.from_namespace(args)
    vault = resolve_vault(override=options.vault)
    cfg = load_config(vault)
    kg = get_kg_backend(vault, cfg)
    sub = options.command

    if sub == "add":
        subject = required_text(options.subject, "subject")
        predicate = required_text(options.predicate, "predicate")
        object_value = required_text(options.object_value, "object")
        kg_cfg = cfg.get("knowledge_graph") or {}
        if bool(kg_cfg.get("fact_check_on_add", True)):
            from lib.fact_checker import conflicting_objects_for_predicate

            conflicts = conflicting_objects_for_predicate(
                kg, subject, predicate, object_value, cfg=cfg
            )
            if conflicts:
                print(
                    "Conflict: active triple(s) already exist for "
                    f"{subject} → {predicate} with different object(s):",
                    file=sys.stderr,
                )
                for t in conflicts:
                    print(f"  → {t.get('o')}  (id={t.get('id')})", file=sys.stderr)
                print(
                    "Invalidate the old fact first, or set knowledge_graph.fact_check_on_add=false",
                    file=sys.stderr,
                )
                return 1
        try:
            tid = kg.add_triple(
                subject,
                predicate,
                object_value,
                valid_from=options.valid_from,
                source=options.source,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"Added: {subject} → {predicate} → {object_value}  (id: {tid})")
        return 0

    if sub == "query":
        entity = required_text(options.entity, "entity")
        results = kg.query_entity(entity, as_of=options.as_of)
        if options.json_out:
            from lib.emit import emit_json

            emit_json({"entity": entity, "facts": results, "count": len(results)})
            return 0
        if not results:
            print(f"No facts found for: {entity}")
            return 0
        for t in results:
            ended = f"  (ended {t['valid_until']})" if t.get("valid_until") else ""
            print(f"  {t['s']} → {t['p']} → {t['o']}  [{t.get('valid_from', '?')}]{ended}")
        return 0

    if sub == "invalidate":
        subject = required_text(options.subject, "subject")
        predicate = required_text(options.predicate, "predicate")
        object_value = required_text(options.object_value, "object")
        ok = kg.invalidate(
            subject,
            predicate,
            object_value,
            ended=options.ended,
        )
        if ok:
            print(f"Invalidated: {subject} → {predicate} → {object_value}")
        else:
            print("No matching active triple found.", file=sys.stderr)
        return 1 if not ok else 0

    if sub == "timeline":
        entity = options.entity
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
        if options.json_out:
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

    if sub == "conflicts":
        from lib.emit import emit_json
        from lib.fact_checker import find_predicate_conflicts

        triples = list(kg.all_triples())
        conflicts = find_predicate_conflicts(triples)
        payload = {
            "count": len(conflicts),
            "conflicts": [
                {
                    "subject": c["subject"],
                    "predicate": c["predicate"],
                    "objects": c["objects"],
                }
                for c in conflicts
            ],
        }
        if options.json_out:
            emit_json(payload)
        else:
            if not conflicts:
                print("No predicate conflicts.")
                return 0
            print(f"{len(conflicts)} conflict(s):")
            for c in conflicts:
                print(
                    f"  {c['subject']} → {c['predicate']} → "
                    + " | ".join(c["objects"])
                )
        return 1 if conflicts else 0

    print(
        "Usage: llm-wiki kg {add|query|invalidate|timeline|stats|rebuild|conflicts}",
        file=sys.stderr,
    )
    return 1


def _resolve_message_preview_for_log(options: MemoryArgs) -> tuple[str | None, int | None]:
    """Return (preview, exit_code). exit_code is set on fatal read errors.

    Prefer ``--message-preview-file`` so hooks avoid shell-quoting issues with
    quotes, newlines, or box-drawing characters in assistant messages.
    """
    fp = options.message_preview_file
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
    inline = options.message_preview
    if inline is not None:
        return inline, None
    return os.environ.get("LLM_WIKI_MESSAGE_PREVIEW"), None


def cmd_memory(args: argparse.Namespace) -> int:
    from lib import session_memory as mem

    options = MemoryArgs.from_namespace(args)
    vault = resolve_vault(override=options.vault)
    cfg = load_config(vault)
    sub = options.command

    def _sid() -> str:
        return mem.resolve_session_arg(
            vault,
            session_id=options.session_id,
            current=options.current,
        )

    if sub == "save":
        if not mem.memory_enabled(cfg):
            print("memory.enabled is false — skipping.", file=sys.stderr)
            return 0
        if not options.current and not options.session_id:
            print("memory save: pass --session-id or --current", file=sys.stderr)
            return 1
        try:
            sid = _sid()
        except (ValueError, FileNotFoundError) as e:
            print(str(e), file=sys.stderr)
            return 1
        tags = None
        raw_tags = options.tags or ""
        if raw_tags.strip():
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        meta = None
        if options.metadata:
            try:
                decoded_meta = cast(object, json.loads(options.metadata))
            except json.JSONDecodeError:
                print("Invalid JSON for --metadata", file=sys.stderr)
                return 1
            if not isinstance(decoded_meta, dict):
                print("--metadata must be a JSON object", file=sys.stderr)
                return 1
            meta = cast(dict[str, object], decoded_meta)
        path = mem.memory_save(
            vault,
            cfg,
            sid,
            summary=options.summary,
            compact_summary=options.compact_summary,
            tags=tags,
            metadata=meta,
        )
        print(path.relative_to(vault))
        return 0

    if sub == "log":
        if not mem.memory_enabled(cfg):
            print("memory.enabled is false — skipping.", file=sys.stderr)
            return 0
        if not options.current and not options.session_id:
            print("memory log: pass --session-id or --current", file=sys.stderr)
            return 1
        try:
            sid = _sid()
        except (ValueError, FileNotFoundError) as e:
            print(str(e), file=sys.stderr)
            return 1
        preview, err = _resolve_message_preview_for_log(options)
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
            session_id=options.session_filter,
            tag=options.tag,
        )
        if options.json_out:
            print(json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(
                    f"{r['session_id']}\t{r.get('updated', '')}\trounds={r.get('rounds', 0)}\t"
                    f"tags={','.join(r.get('tags', []))}"
                )
        return 0

    if sub == "show":
        sid = options.session_id_arg
        if options.current:
            try:
                sid = mem.resolve_current_session(vault)
            except (ValueError, FileNotFoundError) as e:
                print(str(e), file=sys.stderr)
                return 1
        elif not sid:
            print("show: pass SESSION_ID or --current", file=sys.stderr)
            return 1
        text = mem.memory_show(vault, cfg, sid)
        if options.json_out:
            from lib.emit import emit_json

            emit_json({"session_id": sid, "content": text})
            return 0
        print(text, end="" if text.endswith("\n") else "\n")
        return 0

    if sub == "recall":
        q = (options.query or "").strip()
        if not q:
            print("recall: query required", file=sys.stderr)
            return 1
        sf = options.session_filter
        if options.current:
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
            tag=options.tag,
            limit=options.limit or 5,
        )
        if options.json_out:
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
                session_id=options.session_filter,
                tag=options.tag,
                older_than_days=options.older_than,
                keep=options.keep,
                dry_run=options.dry_run,
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

    options = MetricsArgs.from_namespace(args)
    vault = resolve_vault(override=options.vault)
    cfg = load_config(vault)
    cfg.setdefault("metrics", {})["enabled"] = True
    m = MetricsRecorder(vault, cfg)
    sub = options.command

    if sub == "record":
        key = required_text(options.key, "key")
        raw_value = required_text(options.value, "value")
        value: float | int | str = raw_value
        try:
            value = int(raw_value)
        except ValueError:
            try:
                value = float(raw_value)
            except ValueError:
                pass
        meta = None
        if options.meta:
            try:
                decoded_meta = cast(object, json.loads(options.meta))
            except json.JSONDecodeError:
                print(f"Invalid JSON for --meta: {options.meta}", file=sys.stderr)
                return 1
            if not isinstance(decoded_meta, dict):
                print("--meta must be a JSON object", file=sys.stderr)
                return 1
            meta = cast(dict[str, object], decoded_meta)
        tags = [tag.strip() for tag in options.tags.split(",") if tag.strip()] if options.tags else None
        m.record(key, value, meta=meta, tags=tags)
        print(f"Recorded: {key}={value}")
        return 0

    if sub == "query":
        records = m.query(
            key=options.key,
            since=options.since,
            limit=options.limit or 100,
        )
        if not records:
            print("No records found.")
            return 0
        if options.json_out:
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
        if not options.yes:
            print("Use --yes to confirm clearing metrics.", file=sys.stderr)
            return 1
        result = m.clear(before=options.before)
        print(f"Removed {result['removed']} records.")
        return 0

    if sub == "report":
        from lib.metrics_report import build_metrics_report

        out_arg = options.report_out
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
                since=options.report_since,
                key=options.report_key,
            )
        except FileNotFoundError as e:
            print(e, file=sys.stderr)
            return 1
        print(f"Metrics dashboard → {path}")
        print(f"  cd {path.parent} && python3 -m http.server 8890")
        return 0

    if sub == "summary":
        from lib.metrics_report import build_metrics_summary

        if options.summary_json:
            out = build_metrics_summary(
                vault,
                cfg,
                since=options.summary_since,
                key=options.summary_key,
                as_json=True,
            )
            assert isinstance(out, dict)
            print(json.dumps(out, indent=2))
        else:
            text = build_metrics_summary(
                vault,
                cfg,
                since=options.summary_since,
                key=options.summary_key,
                as_json=False,
            )
            assert isinstance(text, str)
            print(text)
        return 0

    print("Usage: llm-wiki metrics {record|query|stats|clear|report|summary}", file=sys.stderr)
    return 1


def cmd_benchmark(args: argparse.Namespace) -> int:
    """Run retrieval benchmarks (LME, LoCoMo, ConvoMem) and print metrics."""

    root = plugin_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    options = BenchmarkArgs.from_namespace(args)
    vault = resolve_vault(override=options.vault)
    cfg = load_config(vault)
    bcfg = cfg.get("benchmark") or {}
    sub = options.command
    if not bcfg.get("enabled", True) and sub not in ("analyze", "suites"):
        print("benchmark.enabled is false in config.json", file=sys.stderr)
        return 1

    if sub == "suites":
        from benchmarks.suite_help import describe_benchmark_suites

        print(describe_benchmark_suites(), end="")
        return 0

    if sub == "run":
        raw_suite = options.suite or "lme"
        suite = "lme" if raw_suite in ("lme", "longmemeval") else raw_suite
        no_metrics = options.no_metrics
        if no_metrics:
            cfg.setdefault("benchmark", {})["auto_record_metrics"] = False
        compress_arg = options.compress
        compress = compress_arg if compress_arg is not None else bcfg.get("compress_method", "raw")
        backend_arg = options.backend
        backend = backend_arg if backend_arg is not None else (bcfg.get("search") or {}).get("backend", "fts5")
        limit = options.limit or 0
        data_arg = options.data
        top_k = options.top_k or 5

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

            peer_list = options.peers or []
            strict_peers = options.strict_peers or bool(
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

        since = options.since
        records = load_metrics_records(vault, cfg, since=since, limit=0)
        bench = [r for r in records if str(r.get("key", "")).startswith("benchmark.")]
        if options.json_out:
            print(json.dumps(bench[-2000:], indent=2))
            return 0
        for r in bench[-50:]:
            print(f"{r.get('ts', '')[:19]}  {r.get('key')}={r.get('value')}  {r.get('meta', {})}")
        return 0

    if sub == "history":
        from lib.metrics_report import load_metrics_records

        hist_limit = options.history_limit or 30
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
        ia = options.compare_a if options.compare_a is not None else -2
        ib = options.compare_b if options.compare_b is not None else -1
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
        from benchmarks.lme_bench import (
            analyze_lme_failures_log,
            format_lme_failures_analysis,
        )

        suite = options.analyze_suite or "lme"
        if suite != "lme":
            print("benchmark analyze: only --suite lme is supported", file=sys.stderr)
            return 1
        raw_path = options.failures_path
        if raw_path:
            fail_path = Path(str(raw_path)).resolve()
        else:
            results_dir = vault / str(bcfg.get("results_dir") or ".benchmarks")
            fail_path = results_dir / "lme_failures.jsonl"
        summary = analyze_lme_failures_log(fail_path)
        if options.analyze_json:
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
    print("  Search backend: fts5 (ranked) | grep (simple) | chromadb (semantic) | hybrid (FTS+Chroma RRF)")
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
    print("  KG backend: json (simple file) | sqlite (temporal queries)")
    kb = input(f"  KG backend [{kb_cur}]: ").strip().lower()
    if kb in ("json", "sqlite"):
        cfg.setdefault("knowledge_graph", {})["backend"] = kb

    save_config(vault, cfg)
    print("\nSaved.")
    return 0
