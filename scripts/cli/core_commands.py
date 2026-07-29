"""Vault setup, ingest, raw, git, integrations, and related CLI commands."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import webbrowser
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.config_loader import load_config, resolve_storage_path, save_config
from lib.paths import plugin_root, resolve_vault
from lib import git as vgit
from lib.search import get_search_backend
from lib.sitegen import build_site, collect_wiki, site_is_stale
from lib.graphgen import build_graph_bundle
from lib.ingest_finish import post_ingest
from lib.raw_markdown import append_preparation_log, raw_file_path
from lib.raw_validate import normalize_raw_relpath, validate_raw_file_result
from lib.research_loop import run_research_loop
from ingest.registry import adapter_map, run_ingest
from ingest import security as secscan

VIEWER_HTTP_PID_NAME = ".viewer-http.pid"


def _viewer_pid_path(og_dir: Path) -> Path:
    return og_dir / VIEWER_HTTP_PID_NAME


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            k = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h:
                return False
            k.CloseHandle(h)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    else:
        return True


def _terminate_pid(pid: int) -> bool:
    if sys.platform == "win32":
        r = subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return r.returncode == 0
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except ProcessLookupError:
        return False


def cmd_stop_viewer_http(vault: Path) -> int:
    """Stop background http.server recorded in ``wiki/.og/.viewer-http.pid``."""
    og_dir = vault / "wiki" / ".og"
    pid_path = _viewer_pid_path(og_dir)
    if not pid_path.is_file():
        print(
            "No background viewer recorded for this vault "
            f"(expected wiki/.og/{VIEWER_HTTP_PID_NAME}).",
            file=sys.stderr,
        )
        return 1
    try:
        line = pid_path.read_text(encoding="utf-8").strip().splitlines()[0]
        pid = int(line.strip())
    except (OSError, ValueError, IndexError) as e:
        print(f"Invalid pid file {pid_path}: {e}", file=sys.stderr)
        try:
            pid_path.unlink()
        except OSError:
            pass
        return 1
    if not _pid_is_running(pid):
        try:
            pid_path.unlink()
        except OSError:
            pass
        print(f"Removed stale pid file (process {pid} was not running).")
        return 0
    if _terminate_pid(pid):
        try:
            pid_path.unlink()
        except OSError:
            pass
        print(f"Stopped viewer HTTP server (PID {pid}).")
        return 0
    print(f"Could not stop process {pid}.", file=sys.stderr)
    return 1


def cmd_sync_agent_docs(args: argparse.Namespace) -> int:
    """Regenerate AGENTS.md / rules from docs/AGENTS.shared.md (plugin repo only)."""
    from sync_agent_docs import sync_agent_docs, verify_agent_docs

    root = plugin_root()
    if getattr(args, "check", False):
        return verify_agent_docs(root)
    return sync_agent_docs(root)


def cmd_configure(args: argparse.Namespace) -> int:
    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    if args.wiki_root:
        cfg["wiki_root"] = args.wiki_root
    if args.og_base_url is not None:
        cfg.setdefault("viewer", {})["og_base_url"] = args.og_base_url
    if getattr(args, "persona_name", None) is not None:
        cfg.setdefault("persona", {})["name"] = args.persona_name
    for key, sec in [
        ("viewer", "viewer_enabled"),
        ("git", "git_enabled"),
        ("research_loop", "research_enabled"),
        ("ingestion_security", "security_enabled"),
    ]:
        val = getattr(args, sec, None)
        if val is not None:
            cfg.setdefault(key, {})["enabled"] = val
    save_config(vault, cfg)
    print(f"Wrote {vault / 'config.json'}")
    return 0


def _yn(prompt: str, default: bool) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = input(f"{prompt} [{hint}]: ").strip().lower()
    if raw in ("y", "yes"):
        return True
    if raw in ("n", "no"):
        return False
    return default


def _setup_wizard(vault: Path, cfg: dict) -> None:
    """Interactive setup wizard — asks about features with explanations."""
    print()
    print("╭─────────────────────────────────────╮")
    print("│  llm-wiki setup wizard              │")
    print("╰─────────────────────────────────────╯")
    print()
    print("  Use defaults for a quick start, or step through")
    print("  each feature to customize your vault.")
    print()

    mode = input("  (d) Defaults — fast, change later  /  (s) Step-by-step: ").strip().lower()
    if mode not in ("s", "step", "step-by-step"):
        print("\n  Using defaults. Run `llm-wiki configure -i` to change later.\n")
        return

    print()
    cur_name = (cfg.get("persona") or {}).get("name") or "Gennie"
    pn = input(f"  Wiki persona name [{cur_name}]: ").strip()
    if pn:
        cfg.setdefault("persona", {})["name"] = pn

    print()
    print("─── Core features ───")
    print()

    if _yn(
        "  Enable vault git? (track changes to wiki/, raw/, config)\n"
        "  Good for: undo mistakes, see what changed between sessions.\n"
        "  Enable",
        default=True,
    ):
        cfg.setdefault("git", {})["enabled"] = True
        cfg["git"]["init_on_setup"] = True
    else:
        cfg.setdefault("git", {})["enabled"] = False

    print()
    if _yn(
        "  Enable static viewer? (browse your wiki in a local web page)\n"
        "  Good for: visual overview, sharing with teammates.\n"
        "  Enable",
        default=True,
    ):
        cfg.setdefault("viewer", {})["enabled"] = True
    else:
        cfg.setdefault("viewer", {})["enabled"] = False

    print()
    if _yn(
        "  Enable ingestion security? (scans URLs + content for threats)\n"
        "  Good for: catching malicious prompt injections in ingested content.\n"
        "  Enable",
        default=True,
    ):
        cfg.setdefault("ingestion_security", {})["enabled"] = True
    else:
        cfg.setdefault("ingestion_security", {})["enabled"] = False

    print()
    print("─── MCP server (lets agents query your wiki via tools) ───")
    print()
    print("  The MCP server gives AI agents direct access to your wiki")
    print("  through 33 tools: search, knowledge graph, ingest, validate, memory, metrics, benchmarks.")
    print("  Without it, agents must shell out to the CLI for every operation.")
    print()
    if _yn("  Enable MCP server", default=True):
        cfg.setdefault("mcp", {})["enabled"] = True
    else:
        cfg.setdefault("mcp", {})["enabled"] = False

    print()
    print("─── Search backend ───")
    print()
    print("  (fts5)  SQLite FTS5 — BM25 ranked search, phrase matching,")
    print("          boolean queries. Zero deps (Python stdlib). [recommended]")
    print("  (grep)  Ripgrep / regex — fast literal search, no ranking.")
    print("          Simplest option, no index file.")
    print("  (chromadb) Semantic embeddings — finds conceptually similar content")
    print("          even without keyword overlap. Requires: pip install chromadb")
    print("  (hybrid)   FTS5 + Chroma reciprocal-rank fusion — needs chromadb;")
    print("          falls back to fts5 if Chroma is unavailable.")
    print()
    sb = input("  Search backend [fts5]: ").strip().lower() or "fts5"
    if sb in ("fts5", "grep", "chromadb", "hybrid"):
        cfg.setdefault("mcp", {})["search_backend"] = sb
    else:
        print(f"  Unknown backend '{sb}', using fts5.")
        cfg.setdefault("mcp", {})["search_backend"] = "fts5"

    print()
    print("─── Knowledge graph ───")
    print()
    print("  Tracks entity relationships (who decided what, project dependencies,")
    print("  team assignments) extracted from your wiki and raw files.")
    print()
    if _yn("  Enable knowledge graph", default=True):
        cfg.setdefault("knowledge_graph", {})["enabled"] = True
        print()
        print("  (json)   JSON file — zero deps, simple, readable.")
        print("           Stored in .kg.json alongside your vault files.")
        print("  (sqlite) SQLite — better for large wikis (1000+ facts),")
        print("           temporal queries (what was true on date X). Stdlib.")
        print()
        kb = input("  KG backend [json]: ").strip().lower() or "json"
        if kb in ("json", "sqlite"):
            cfg["knowledge_graph"]["backend"] = kb
        else:
            print(f"  Unknown backend '{kb}', using json.")
            cfg["knowledge_graph"]["backend"] = "json"
    else:
        cfg.setdefault("knowledge_graph", {})["enabled"] = False

    print()
    if _yn(
        "  Enable research loop? (batch web research from a task list)\n"
        "  Good for: automated research across multiple topics.\n"
        "  Enable",
        default=False,
    ):
        cfg.setdefault("research_loop", {})["enabled"] = True
    else:
        cfg.setdefault("research_loop", {})["enabled"] = False

    save_config(vault, cfg)
    print()
    print("  Settings saved to config.json.")
    print("  Change anytime with: llm-wiki configure -i")
    print()


def cmd_setup(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    vault = root / "llm-wiki"
    if args.vault:
        vault = Path(args.vault).resolve()
    tpl = plugin_root() / "templates" / "llm-wiki"
    if not tpl.is_dir():
        print("Template missing:", tpl, file=sys.stderr)
        print(
            "Vault scaffolding needs a git clone or marketplace plugin install "
            "(templates/ is not shipped in the CLI/MCP wheel).",
            file=sys.stderr,
        )
        print(
            "See docs/INSTALL.md — use ./bin/llm-wiki setup from a full checkout.",
            file=sys.stderr,
        )
        return 1
    shutil.copytree(tpl, vault, dirs_exist_ok=True)
    cfg = load_config(vault)

    if getattr(args, "interactive", False) or (
        sys.stdin.isatty() and not getattr(args, "defaults", False)
    ):
        _setup_wizard(vault, cfg)
        cfg = load_config(vault)

    if cfg.get("git", {}).get("init_on_setup"):
        try:
            print(vgit.git_init(vault, cfg))
        except vgit.GitDisabledError:
            pass
    print(f"Scaffolded vault at {vault}")
    print("\nNext: add hooks for automatic Memory Stack updates.")
    print(f"  See: {plugin_root() / 'hooks' / 'README.md'}")
    return 0


def cmd_teardown(args: argparse.Namespace) -> int:
    vault = resolve_vault(override=args.vault)
    og = vault / "wiki" / ".og"
    if args.purge:
        if not args.yes:
            print("Refusing --purge without --yes", file=sys.stderr)
            return 1
        shutil.rmtree(vault, ignore_errors=True)
        print("Removed vault directory.")
        return 0
    if getattr(args, "artifacts", False):
        if not args.yes:
            print("Refusing --artifacts without --yes", file=sys.stderr)
            return 1
        cfg = load_config(vault)
        vault_root = vault.resolve()
        candidates = [
            vault / ".kg.json",
            vault / ".kg.sqlite3",
            vault / "raw" / ".hashes.json",
            vault / "raw" / ".tags.json",
            resolve_storage_path(vault, cfg, "search_db"),
            resolve_storage_path(vault, cfg, "kg_db"),
            resolve_storage_path(vault, cfg, "kg_sqlite_db"),
            resolve_storage_path(vault, cfg, "chromadb_dir"),
            resolve_storage_path(vault, cfg, "metrics_db"),
        ]
        paths: list[Path] = []
        for path in candidates:
            try:
                path.resolve().relative_to(vault_root)
            except ValueError:
                print(f"Skipping index outside vault: {path}", file=sys.stderr)
                continue
            if path not in paths:
                paths.append(path)
            if path.suffix in {".sqlite3", ".db"}:
                paths.extend([Path(f"{path}-wal"), Path(f"{path}-shm")])
        for path in paths:
            if not path.exists():
                continue
            if args.dry_run:
                print(f"Would remove {path}")
            elif path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
                print(f"Removed {path}")
            else:
                path.unlink(missing_ok=True)
                print(f"Removed {path}")
        return 0
    if og.is_dir():
        if args.dry_run:
            print(f"Would remove {og}")
        else:
            shutil.rmtree(og, ignore_errors=True)
            print(f"Removed {og}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Search vault content through the configured search backend."""
    vault = resolve_vault(override=args.vault)
    backend = get_search_backend(vault, load_config(vault))
    results = backend.search(
        args.query,
        limit=args.limit,
        tag=args.tag or None,
        scope=args.scope,
    )
    print(
        json.dumps(
            {
                "results": [result.to_dict() for result in results],
                "count": len(results),
                "backend": backend.index_status().get("backend", "unknown"),
            },
            indent=2,
        )
    )
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    out = Path(args.out).resolve() if getattr(args, "out", None) else (vault / ".tmp" / "llm-wiki-graph").resolve()
    mode = getattr(args, "mode", "links")
    try:
        path = build_graph_bundle(vault, cfg, out, mode)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1
    print(f"Graph bundle → {path}")
    port = int((cfg.get("graph") or {}).get("port") or 8890)
    print(f"  python3 -m http.server {port} --directory {path}")
    return 0


def cmd_graph_knowledge(args: argparse.Namespace) -> int:
    args.mode = "knowledge"
    return cmd_graph(args)


def _serve_viewer_http(og_dir: Path, port: int, *, background: bool, open_browser: bool) -> int:
    """Serve ``og_dir`` with ``python -m http.server`` (foreground or detached)."""
    if not og_dir.is_dir():
        print(f"Viewer directory missing: {og_dir}", file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{port}/"
    if background:
        pid_path = _viewer_pid_path(og_dir)
        if pid_path.is_file():
            try:
                old_line = pid_path.read_text(encoding="utf-8").strip().splitlines()[0]
                old_pid = int(old_line.split()[0])
            except (OSError, ValueError, IndexError):
                old_pid = -1
            if old_pid > 0 and _pid_is_running(old_pid):
                print(
                    f"Background viewer already running (PID {old_pid}). "
                    f"Stop with: llm-wiki build-og --stop-serving",
                    file=sys.stderr,
                )
                return 1
            try:
                pid_path.unlink()
            except OSError:
                pass
        popen_kw: dict = {
            "args": [sys.executable, "-m", "http.server", str(port)],
            "cwd": str(og_dir),
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            cf = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if cf:
                popen_kw["creationflags"] = cf
        else:
            popen_kw["start_new_session"] = True
        proc = subprocess.Popen(**popen_kw)
        try:
            pid_path.write_text(f"{proc.pid}\n", encoding="utf-8")
        except OSError as e:
            print(f"Warning: could not write {pid_path}: {e}", file=sys.stderr)
        print(
            f"Serving viewer → {url} (PID {proc.pid}; stop: llm-wiki build-og --stop-serving)",
        )
        if open_browser and not webbrowser.open(url):
            print(f"Could not open browser automatically; visit {url}", file=sys.stderr)
        return 0
    print(f"Serving viewer → {url} (Ctrl+C to stop)")
    if open_browser:
        # Start the server first so browser requests do not race the listener.
        proc = subprocess.Popen([sys.executable, "-m", "http.server", str(port)], cwd=str(og_dir))
        if not webbrowser.open(url):
            print(f"Could not open browser automatically; visit {url}", file=sys.stderr)
        try:
            return proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait()
            print("", file=sys.stderr)
            return 0
    try:
        return subprocess.run(
            [sys.executable, "-m", "http.server", str(port)],
            cwd=str(og_dir),
        ).returncode
    except KeyboardInterrupt:
        print("", file=sys.stderr)
        return 0


def cmd_build_site(args: argparse.Namespace) -> int:
    vault = resolve_vault(override=args.vault)
    stop_serving = getattr(args, "stop_serving", False)
    serve = getattr(args, "serve", False)
    serve_bg = getattr(args, "serve_background", False)
    open_browser = getattr(args, "open", False)
    if stop_serving:
        if serve or serve_bg or open_browser:
            print(
                "Cannot combine --stop-serving with --serve, --serve-background, or --open.",
                file=sys.stderr,
            )
            return 2
        return cmd_stop_viewer_http(vault)
    if open_browser and not (serve or serve_bg):
        print("--open requires --serve or --serve-background.", file=sys.stderr)
        return 2
    cfg = load_config(vault)
    if serve and serve_bg:
        print("Note: --serve-background wins over --serve.", file=sys.stderr)
        serve = False
    port_arg = getattr(args, "port", None)
    viewer = cfg.get("viewer") or {}
    if (serve or serve_bg) and viewer.get("enabled") is False:
        print(
            "viewer.enabled is false; build skipped and cannot --serve. "
            "Enable the viewer or run without --serve/--serve-background.",
            file=sys.stderr,
        )
        return 1
    if getattr(args, "if_stale", False) and not site_is_stale(vault):
        print("Site is up-to-date; skipping build.")
        out = vault / "wiki" / ".og"
    else:
        out = build_site(vault, cfg)
        print(f"Built site → {out}")
        if cfg.get("git", {}).get("snapshot_after_build"):
            try:
                pfx = vgit.prefix_for_phase(cfg, "build") or "[build]"
                msg = f"{pfx} wiki/.og static viewer"
                print(vgit.git_snapshot(vault, cfg, msg))
            except vgit.GitDisabledError:
                pass
            except Exception as e:
                print("git snapshot (after build):", e, file=sys.stderr)
    if serve or serve_bg:
        port = port_arg if port_arg is not None else int(viewer.get("port", 8765))
        return _serve_viewer_http(out, port, background=serve_bg, open_browser=open_browser)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    vault = resolve_vault(override=args.vault)
    errs: list[str] = []
    for p in [vault / "config.json", vault / "wiki" / "index.md", vault / "CLAUDE.md"]:
        if not p.is_file():
            errs.append(f"missing {p.relative_to(vault) if vault in p.parents or p == vault else p}")
    try:
        cfg = load_config(vault)
    except json.JSONDecodeError as e:
        print(f"Invalid config.json: {e}", file=sys.stderr)
        return 1
    try:
        json.dumps(cfg)
    except Exception as e:
        errs.append(f"config not JSON-serializable: {e}")
    if getattr(args, "wikilinks", False):
        graph = collect_wiki(vault, cfg)
        ids = {n["id"] for n in graph.get("nodes", [])}
        seen: set[tuple[str, str, str]] = set()
        for e in graph.get("edges", []):
            tgt = e.get("target")
            src = e.get("source")
            if tgt not in ids:
                key = (str(src), str(tgt), str(e.get("kind", "")))
                if key not in seen:
                    errs.append(f"broken wikilink from {src} → {tgt}")
                    seen.add(key)
    if getattr(args, "schema", False) or (cfg.get("compile") or {}).get("schema_required"):
        from lib.wiki_schema import SCHEMA_EXEMPT_NAMES, validate_page_schema

        wiki = vault / "wiki"
        require_sources = bool((cfg.get("compile") or {}).get("require_sources", True))
        require_updated = bool((cfg.get("compile") or {}).get("require_updated", False))
        if wiki.is_dir():
            for path in wiki.rglob("*.md"):
                if ".og" in path.parts or path.name in SCHEMA_EXEMPT_NAMES:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                for msg in validate_page_schema(
                    path,
                    text,
                    require_sources=require_sources,
                    require_updated=require_updated,
                ):
                    rel = path.relative_to(wiki).as_posix()
                    errs.append(f"schema {rel}: {msg}")
    if errs:
        print("Validation issues:", *errs, sep="\n  - ", file=sys.stderr)
        return 1
    print("OK")
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    from lib.emit import emit_json
    from lib.wiki_lint import lint_vault, write_lint_report

    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    report = lint_vault(
        vault,
        cfg,
        check_schema=True if getattr(args, "schema", False) else None,
        check_stale=not getattr(args, "no_stale", False),
        check_outputs=not getattr(args, "no_outputs", False),
    )
    if getattr(args, "write_report", False):
        path = write_lint_report(vault, report)
        report["report_path"] = str(path)
    if getattr(args, "json_out", False):
        emit_json(report)
    else:
        counts = report.get("counts") or {}
        print(f"lint: {counts.get('issues', 0)} issue(s)  ok={report.get('ok')}")
        for it in report.get("issues") or []:
            print(f"  [{it.get('code')}] {it.get('path')}: {it.get('message')}")
        missing = report.get("coverage_missing_tags") or []
        if missing:
            print(f"  coverage: {len(missing)} tag(s) without matching wiki page stem")
            for t in missing[:15]:
                print(f"    - {t}")
        if report.get("report_path"):
            print(f"  wrote {report['report_path']}")
    return 0 if report.get("ok") else 1


def cmd_diff(args: argparse.Namespace) -> int:
    from lib.emit import emit_json
    from lib.wiki_diff import format_diff_text, knowledge_diff, write_diff_json

    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    since = getattr(args, "since", None) or "HEAD~1"
    report = knowledge_diff(vault, cfg, since=since)
    if getattr(args, "write_report", False):
        path = write_diff_json(vault, report)
        report["report_path"] = str(path)
    if getattr(args, "json_out", False):
        emit_json(report)
    else:
        sys.stdout.write(format_diff_text(report))
        if report.get("report_path"):
            print(f"wrote {report['report_path']}")
    return 0 if report.get("ok") else 1


def cmd_compile(args: argparse.Namespace) -> int:
    """Run knowledge CI gates after agent/wiki merge (lint + validate + optional KG)."""
    from lib.compile_pipeline import run_compile

    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    raw = (getattr(args, "raw", "") or "").strip() or None
    result = run_compile(
        vault,
        cfg,
        skip_kg=getattr(args, "no_kg", False),
        skip_site=getattr(args, "no_site", False),
        strict_schema=getattr(args, "schema", False),
        json_out=getattr(args, "json_out", False),
        raw_path=raw,
    )
    return int(result.get("exit_code", 1))


def cmd_knowledge_test(args: argparse.Namespace) -> int:
    """Run knowledge regression tests (claim contains/absent) against wiki/."""
    from lib.emit import emit_json
    from lib.knowledge_tests import load_knowledge_tests, run_knowledge_tests
    from lib.paths import plugin_root

    vault = resolve_vault(override=args.vault)
    path = Path(getattr(args, "file", "") or "")
    if not path.is_file():
        # default fixture path under vault or plugin examples
        candidates = [
            vault / "knowledge-tests.json",
            vault / "outputs" / "knowledge-tests.json",
            plugin_root() / "examples" / "knowledge-tests.json",
        ]
        for c in candidates:
            if c.is_file():
                path = c
                break
    if not path.is_file():
        print(
            "knowledge-test: provide --file PATH (JSON list of {id,path,contains})",
            file=sys.stderr,
        )
        return 1
    tests = load_knowledge_tests(path)
    report = run_knowledge_tests(vault, tests)
    report["file"] = str(path)
    if getattr(args, "json_out", False):
        emit_json(report)
    else:
        print(f"knowledge-test: {report['total'] - report['failed']}/{report['total']} passed")
        for r in report.get("results") or []:
            mark = "ok" if r.get("ok") else "FAIL"
            detail = f" — {r.get('detail')}" if r.get("detail") else ""
            print(f"  [{mark}] {r.get('id')}{detail}")
    return 0 if report.get("ok") else 1


def _raw_validate_run(vault: Path, rel: str, autofix: bool) -> tuple[bool, Path, list[str]]:
    """
    Validate one file under raw/. If autofix, apply deterministic fixes first.
    Returns (ok, absolute_path, autofix_descriptions).
    """
    cfg = load_config(vault)
    r = validate_raw_file_result(vault, cfg, rel, autofix=autofix)
    if r.get("error"):
        print(r["error"], file=sys.stderr)
        p = r.get("path_obj")
        if p is None:
            return False, vault / "raw" / rel.replace("\\", "/"), []
        return False, p, []
    path = r["path_obj"]
    assert path is not None
    if r.get("skipped"):
        print("OK (skipped — session memory)", path.relative_to(vault))
        return True, path, []
    applied = r.get("autofix_applied") or []
    if applied:
        print("Autofix:", *applied, sep="\n  - ")
    issues = r.get("issues") or []
    if issues:
        print("Issues:", *issues, sep="\n  - ", file=sys.stderr)
        return False, path, applied
    print("OK", path.relative_to(vault))
    return True, path, applied


def cmd_raw_validate(args: argparse.Namespace) -> int:
    vault = resolve_vault(override=args.vault)
    rel = normalize_raw_relpath(args.path)
    ok, _, _ = _raw_validate_run(vault, rel, getattr(args, "autofix", False))
    return 0 if ok else 1


def cmd_raw_finish(args: argparse.Namespace) -> int:
    """
    Autofix (optional) + validate + preparation log + optional git snapshot (--phase prepare).
    LLM formatting must be done in the editor/chat before running finish.
    """
    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    rel = normalize_raw_relpath(args.path)
    autofix = getattr(args, "autofix", True)
    ok, path, applied = _raw_validate_run(vault, rel, autofix)
    if not ok:
        print(
            "raw finish: fix structural issues or edit the file (e.g. wiki-raw-prepare), then retry.",
            file=sys.stderr,
        )
        return 1
    rac = getattr(args, "record_action", None)
    if rac is None:
        rac = "autofixed" if applied else "validated"
    goal = getattr(args, "goal", None) or args.message
    log = append_preparation_log(
        vault,
        rel_path=rel,
        goal=goal,
        action=rac,
        notes=getattr(args, "notes", "") or "",
    )
    print(f"Logged → {log.relative_to(vault)}")
    if getattr(args, "skip_git", False):
        return 0
    if not cfg.get("git", {}).get("enabled"):
        print(
            "Vault git disabled — skipped commit. Enable git.enabled, then re-run or: "
            "llm-wiki git snapshot -m \"…\" --phase prepare",
        )
        return 0
    pfx = vgit.prefix_for_phase(cfg, "prepare") or "[prepare]"
    msg = f"{pfx} {args.message}".strip()
    print(vgit.git_snapshot(vault, cfg, msg))
    return 0


def cmd_raw_record(args: argparse.Namespace) -> int:
    vault = resolve_vault(override=args.vault)
    rel = normalize_raw_relpath(args.path)
    p = raw_file_path(vault, rel)
    if not p.is_file():
        print(f"Warning: no file at {p} (record still appended)", file=sys.stderr)
    log = append_preparation_log(
        vault,
        rel_path=rel,
        goal=args.goal,
        action=args.action,
        notes=getattr(args, "notes", "") or "",
    )
    print(f"Logged → {log.relative_to(vault)}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    argv = args.adapter_args
    if args.list:
        for cls in adapter_map().values():
            print(f"  {cls.id:12} {cls.label}")
        return 0
    if not argv:
        print("Usage: llm-wiki ingest <adapter> [adapter-args…]", file=sys.stderr)
        print("       llm-wiki ingest --list", file=sys.stderr)
        return 1
    adapter_id = argv[0]
    rest = argv[1:]
    try:
        result = run_ingest(vault, cfg, adapter_id, rest, force_adapter=args.force)
    except SystemExit as e:
        print(e, file=sys.stderr)
        c = e.code
        return int(c) if isinstance(c, int) else 1
    print(result.message)
    manual_tags = [t.strip() for t in args.tags.split(",") if t.strip()] if getattr(args, "tags", "") else []
    return post_ingest(
        vault,
        cfg,
        result.output_path,
        force=args.force,
        force_security=args.force_security,
        commit_body=result.commit_body,
        manual_tags=manual_tags,
    )


def cmd_deps(args: argparse.Namespace) -> int:
    """Fail fast if Vision PDF ingest deps are missing."""
    from ingest.adapters.pdf_vision import pdf_vision_preflight

    msg = pdf_vision_preflight()
    if msg:
        print(msg, file=sys.stderr)
        return 1
    print("PDF ingest deps: ok (pdf2image, anthropic, poppler, ANTHROPIC_API_KEY).")
    return 0


def _claude_settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def _read_claude_settings() -> dict:
    p = _claude_settings_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def _write_claude_settings(data: dict) -> None:
    p = _claude_settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _set_integration_key(env_var: str, key_value: str) -> None:
    """Persist an API key in ~/.claude/settings.json env block."""
    data = _read_claude_settings()
    data.setdefault("env", {})[env_var] = key_value
    _write_claude_settings(data)
    # Also export for current process so subsequent checks pass
    os.environ[env_var] = key_value


# Map adapter id → the env var name it uses (for the wizard)
_INTEGRATION_ENV: dict[str, str] = {
    "firecrawl": "FIRECRAWL_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "hackernews": "",          # no key needed
    "url": "",                 # no key needed
    "youtube": "",             # no key needed
    "twitter": "TWITTER_AUTH_TOKEN",
    "brave": "BRAVE_SEARCH_API_KEY",
}

_INTEGRATION_HINT: dict[str, str] = {
    "firecrawl": "Get key: https://firecrawl.dev/app/api-keys  |  Or: npm install -g firecrawl-cli && firecrawl login",
    "playwright": "pip install playwright && playwright install chromium  |  Optional: Playwright MCP in Cursor/Claude for interactive browsing (separate from vault MCP)",
    "perplexity": "Get key: https://www.perplexity.ai/settings/api",
    "twitter": "Get auth_token cookie from browser DevTools → Application → Cookies → auth_token  |  Install: npm install -g @steipete/bird  |  Zero-config for public tweets (no token needed)",
    "brave": "Get free key: https://api.search.brave.com  |  Modes: web | news | llm-context (RAG) | answers",
}


def cmd_integrations(args: argparse.Namespace) -> int:
    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    sub = args.integrations_cmd
    integrations = cfg.get("integrations") or {}

    if sub == "status":
        for cls in adapter_map().values():
            slice_ = integrations.get(cls.id) or {}
            en = slice_.get("enabled", True) if cls.id in integrations else True
            warns = cls.setup_checks(slice_)
            w = "; ".join(warns) if warns else "ok"
            print(f"{cls.id:14} enabled={str(en):<5}  {w}")
        return 0

    if sub == "validate":
        bad = False
        for cls in adapter_map().values():
            slice_ = integrations.get(cls.id) or {}
            for w in cls.setup_checks(slice_):
                print(f"{cls.id}: {w}")
                bad = True
        return 1 if bad else 0

    if sub == "set-key":
        adapter_id = args.adapter
        key_value = args.key_value
        env_var = _INTEGRATION_ENV.get(adapter_id)
        if not env_var:
            print(f"No env var known for '{adapter_id}'. Known: {[k for k,v in _INTEGRATION_ENV.items() if v]}")
            return 1
        _set_integration_key(env_var, key_value)
        # Also enable in config.json
        cfg.setdefault("integrations", {}).setdefault(adapter_id, {})["enabled"] = True
        save_config(vault, cfg)
        print(f"Set {env_var} in ~/.claude/settings.json and enabled {adapter_id} in config.json.")
        return 0

    if sub == "wizard":
        print("╔═══════════════════════════════════════════════════════╗")
        print("║         llm-wiki  Integrations Setup Wizard           ║")
        print("╚═══════════════════════════════════════════════════════╝")
        print()
        changed = False
        from lib.emit import fail_mark, ok_mark

        for cls in sorted(adapter_map().values(), key=lambda c: c.id):
            slice_ = integrations.get(cls.id) or {}
            warns = cls.setup_checks(slice_)
            status = f"{ok_mark()} ok" if not warns else f"{fail_mark()} " + warns[0]
            env_var = _INTEGRATION_ENV.get(cls.id, "")
            print(f"  {cls.id:14}  {status}")
            if warns and env_var:
                hint = _INTEGRATION_HINT.get(cls.id, "")
                if hint:
                    print(f"               {hint}")
                cur_in_settings = (_read_claude_settings().get("env") or {}).get(env_var, "")
                masked = f"{cur_in_settings[:8]}…" if len(cur_in_settings) > 8 else cur_in_settings
                prompt = f"               Enter {env_var}{' ['+masked+']' if masked else ''} (blank to skip): "
                try:
                    val = input(prompt).strip()
                except EOFError:
                    val = ""
                if val:
                    _set_integration_key(env_var, val)
                    cfg.setdefault("integrations", {}).setdefault(cls.id, {})["enabled"] = True
                    print(f"               {ok_mark()} Saved to ~/.claude/settings.json")
                    changed = True
            elif warns and not env_var:
                hint = _INTEGRATION_HINT.get(cls.id, "")
                if hint:
                    print(f"               {hint}")
            elif not warns:
                en = slice_.get("enabled", True)
                try:
                    v = input(f"               Enable {cls.id}? (y/n) [{'y' if en else 'n'}]: ").strip().lower()
                except EOFError:
                    v = ""
                if v in ("y", "n"):
                    cfg.setdefault("integrations", {}).setdefault(cls.id, {})["enabled"] = v == "y"
                    changed = True
            print()
        if changed:
            save_config(vault, cfg)
            print("config.json updated.")
        print("Next: llm-wiki integrations validate  →  llm-wiki ingest <adapter> <url>")
        return 0

    print("Use: llm-wiki integrations status|validate|wizard|set-key <adapter> <key>")
    return 0


def cmd_git(args: argparse.Namespace) -> int:
    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    sub = args.git_cmd
    try:
        if sub == "init":
            print(vgit.git_init(vault, cfg))
        elif sub == "status":
            print(vgit.git_status(vault, cfg))
        elif sub == "log":
            print(vgit.git_log(vault, cfg, n=args.n, since=args.since, grep=args.grep))
        elif sub == "diff":
            print(vgit.git_diff(vault, cfg, staged=args.staged))
        elif sub == "snapshot":
            if not args.message:
                print("--message required", file=sys.stderr)
                return 1
            msg = args.message
            if args.phase:
                pfx = vgit.prefix_for_phase(cfg, args.phase)
                if not pfx:
                    print(
                        f"Unknown lifecycle phase {args.phase!r}. Configure git.lifecycle.phases in config.json.",
                        file=sys.stderr,
                    )
                    return 1
                msg = f"{pfx} {msg}"
            print(vgit.git_snapshot(vault, cfg, msg))
        elif sub == "lifecycle":
            rows = vgit.git_lifecycle_audit(
                vault,
                cfg,
                n=args.n,
                phase=args.phase,
                since=args.since,
            )
            if getattr(args, "lifecycle_json", False):
                print(json.dumps(rows, indent=2))
            else:
                print(f"{'date':<12} {'phase':<12} subject")
                for r in rows:
                    subj = (r.get("subject") or "")[:100]
                    print(f"{r.get('date', ''):<12} {r.get('phase', ''):<12} {subj}")
        elif sub == "query":
            vgit.print_git_log_json(vault, cfg, n=args.n)
        else:
            return 1
    except vgit.GitDisabledError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


def cmd_research_loop_cli(args: argparse.Namespace) -> int:
    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    return run_research_loop(
        vault,
        cfg,
        task_id=args.task,
        dry_run=args.dry_run,
        force_adapter=args.force,
    )


def cmd_security(args: argparse.Namespace) -> int:
    path = Path(args.file).resolve()
    if not path.is_file():
        print("Not a file:", path, file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8", errors="replace")
    r = secscan.scan_text(text)
    print(json.dumps(r.to_dict(), indent=2))
    return 0


def cmd_wakeup(args: argparse.Namespace) -> int:
    from lib.layers import build_wake_up, update_claude_md

    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    blob = build_wake_up(vault, cfg)
    print(blob)
    if args.update_claude:
        update_claude_md(vault, cfg)
        print("Updated CLAUDE.md ## Memory Stack.", file=sys.stderr)
    return 0


def cmd_list_topics(args: argparse.Namespace) -> int:
    from lib.layers import wiki_page_for_tag

    vault = resolve_vault(override=args.vault)
    p: Path | None = None
    for candidate in (vault / "raw" / ".tags.json", vault / "llm-wiki" / "raw" / ".tags.json"):
        if candidate.exists():
            p = candidate
            break
    if p is None or not p.exists():
        print("No tag index found. Run: llm-wiki ingest ... --tags <topics>")
        return 0
    index = json.loads(p.read_text(encoding="utf-8"))
    rows = sorted(index.items(), key=lambda kv: -len(kv[1]))
    for tag, files in rows:
        wp = wiki_page_for_tag(vault, tag)
        coverage = f"-> {wp} [covered]" if wp else "no wiki page"
        print(f"  {tag:<20} {len(files):>4} raw files   {coverage}")
    return 0


def cmd_raw_rebuild_index(args: argparse.Namespace) -> int:
    from ingest.dedup import rebuild_index
    from ingest.tagger import rebuild_tag_index

    vault = resolve_vault(override=args.vault)
    h = rebuild_index(vault)
    t = rebuild_tag_index(vault)
    print(f"Rebuilt: {h} hashes, {t} tag entries")
    return 0

