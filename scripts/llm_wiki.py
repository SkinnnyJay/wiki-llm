#!/usr/bin/env python3
"""llm-wiki CLI — Claude Code LLM Wiki plugin."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.config_loader import DEFAULTS, load_config, save_config
from lib.env_loader import load_plugin_dotenv
from lib.paths import plugin_root, resolve_vault
from lib import git as vgit
from lib.sitegen import build_site, collect_wiki, site_is_stale
from lib.graphgen import build_graph_bundle
from lib.ingest_finish import post_ingest
from lib.raw_markdown import append_preparation_log, autofix_raw_markdown, raw_file_path, validate_raw_markdown
from lib.research_loop import run_research_loop
from ingest.registry import adapter_map, run_ingest
from ingest import security as secscan
from lib.self_check import cmd_check, cmd_smoke_test
from lib.test_report import cmd_test_report


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
    print("  through 28 tools: search, knowledge graph, ingest, validate, memory.")
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
    if og.is_dir():
        if args.dry_run:
            print(f"Would remove {og}")
        else:
            shutil.rmtree(og, ignore_errors=True)
            print(f"Removed {og}")
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    out = Path(args.out).resolve() if getattr(args, "out", None) else (Path.cwd() / ".tmp" / "llm-wiki-graph").resolve()
    mode = getattr(args, "mode", "links")
    try:
        path = build_graph_bundle(vault, cfg, out, mode)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1
    print(f"Graph bundle → {path}")
    print(f"  cd {path} && python3 -m http.server 8890")
    return 0


def cmd_graph_knowledge(args: argparse.Namespace) -> int:
    args.mode = "knowledge"
    return cmd_graph(args)


def cmd_build_site(args: argparse.Namespace) -> int:
    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    if getattr(args, "if_stale", False) and not site_is_stale(vault):
        print("Site is up-to-date; skipping build.")
        return 0
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
    if errs:
        print("Validation issues:", *errs, sep="\n  - ", file=sys.stderr)
        return 1
    print("OK")
    return 0


def _normalize_raw_arg(path_arg: str) -> str:
    s = path_arg.replace("\\", "/").strip().lstrip("/")
    if s.startswith("raw/"):
        s = s[4:]
    return s


def _raw_validate_run(vault: Path, rel: str, autofix: bool) -> tuple[bool, Path, list[str]]:
    """
    Validate one file under raw/. If autofix, apply deterministic fixes first.
    Returns (ok, absolute_path, autofix_descriptions).
    """
    path = raw_file_path(vault, rel)
    if not path.is_file():
        print(f"Not a file: {path}", file=sys.stderr)
        return False, path, []
    cfg = load_config(vault)
    mem_dir = (cfg.get("memory") or {}).get("dir", "raw/memory")
    mem_rel = str(Path(mem_dir).as_posix().replace("\\", "/")).strip("/")
    if mem_rel.startswith("raw/"):
        mem_rel = mem_rel[4:]
    if rel == mem_rel or rel.startswith(mem_rel + "/"):
        print("OK (skipped — session memory)", path.relative_to(vault))
        return True, path, []
    text = path.read_text(encoding="utf-8", errors="replace")
    applied: list[str] = []
    if autofix:
        fixed, applied = autofix_raw_markdown(text)
        if applied:
            path.write_text(fixed, encoding="utf-8")
            print("Autofix:", *applied, sep="\n  - ")
        text = path.read_text(encoding="utf-8", errors="replace")
    issues = validate_raw_markdown(text)
    if issues:
        print("Issues:", *issues, sep="\n  - ", file=sys.stderr)
        return False, path, applied
    print("OK", path.relative_to(vault))
    return True, path, applied


def cmd_raw_validate(args: argparse.Namespace) -> int:
    vault = resolve_vault(override=args.vault)
    rel = _normalize_raw_arg(args.path)
    ok, _, _ = _raw_validate_run(vault, rel, getattr(args, "autofix", False))
    return 0 if ok else 1


def cmd_raw_finish(args: argparse.Namespace) -> int:
    """
    Autofix (optional) + validate + preparation log + optional git snapshot (--phase prepare).
    LLM formatting must be done in the editor/chat before running finish.
    """
    vault = resolve_vault(override=args.vault)
    cfg = load_config(vault)
    rel = _normalize_raw_arg(args.path)
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
    rel = _normalize_raw_arg(args.path)
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
        for cls in sorted(adapter_map().values(), key=lambda c: c.id):
            slice_ = integrations.get(cls.id) or {}
            warns = cls.setup_checks(slice_)
            status = "✓ ok" if not warns else "✗ " + warns[0]
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
                    print(f"               ✓ Saved to ~/.claude/settings.json")
                    changed = True
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
    from lib.layers import _wiki_page_for_tag

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
        wp = _wiki_page_for_tag(vault, tag)
        coverage = f"→ {wp} ✓" if wp else "⚠ no wiki page"
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


# ── MCP server ───────────────────────────────────────────────────────────────

def _mcp_tcp_listening(host: str, port: int, *, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _terminate_child_process(proc: subprocess.Popen, *, wait_s: float = 5.0) -> None:
    """Stop a child started for MCP HTTP; no-op if already exited."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=wait_s)
    except subprocess.TimeoutExpired:
        proc.kill()


def _mcp_start_background(args: argparse.Namespace) -> int:
    """
    Ensure the HTTP (SSE) MCP listener is running: if nothing is bound on the
    configured host/port, spawn ``llm-wiki mcp --transport sse`` in the background.
    """
    vault = resolve_vault(override=getattr(args, "vault", None))
    cfg = load_config(vault)
    if not (cfg.get("mcp") or {}).get("enabled", True):
        print(
            "MCP server disabled in config.json (mcp.enabled=false). Enable it to start.",
            file=sys.stderr,
        )
        return 1

    mcp_cfg = cfg.get("mcp") or {}
    port = getattr(args, "mcp_port", None)
    if port is None:
        port = int(mcp_cfg.get("port") or 8891)
    host = getattr(args, "mcp_host", None) or mcp_cfg.get("host") or "127.0.0.1"
    host = str(host)

    url = f"http://{host}:{port}/"
    if _mcp_tcp_listening(host, port):
        print(f"MCP HTTP already listening — {url}")
        return 0

    lock_path = vault / ".mcp-sse-start.lock"
    lock_fd = open(lock_path, "a+", encoding="utf-8")
    try:
        if sys.platform != "win32":
            import fcntl

            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        # Another concurrent `mcp start` may have finished while we waited for the lock.
        if _mcp_tcp_listening(host, port):
            print(f"MCP HTTP already listening — {url}")
            return 0

        root = plugin_root()
        script = root / "scripts" / "llm_wiki.py"
        log_path = vault / ".mcp-sse.log"
        env = os.environ.copy()
        env["LLM_WIKI_VAULT"] = str(vault.resolve())

        cmd = [
            sys.executable,
            str(script),
            "mcp",
            "--transport",
            "sse",
            "--port",
            str(port),
            "--host",
            host,
        ]

        log_file = open(log_path, "ab", buffering=0)
        popen_kw: dict = {
            "cwd": str(root),
            "env": env,
            "stdin": subprocess.DEVNULL,
            "stdout": log_file,
            "stderr": subprocess.STDOUT,
        }
        if sys.platform == "win32":
            # Background process without a console; child keeps inherited log fd.
            popen_kw["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
                subprocess, "DETACHED_PROCESS", 0
            )
        else:
            popen_kw["start_new_session"] = True

        try:
            proc = subprocess.Popen(cmd, **popen_kw)
        except OSError as e:
            log_file.close()
            print(f"Failed to start MCP: {e}", file=sys.stderr)
            return 1

        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            if _mcp_tcp_listening(host, port):
                print(f"Started MCP HTTP in background — {url}")
                print(f"Log: {log_path}")
                return 0
            if proc.poll() is not None:
                log_file.close()
                print(
                    f"MCP server exited immediately (exit code {proc.returncode}). See {log_path}",
                    file=sys.stderr,
                )
                return 1
            time.sleep(0.15)

        print(
            f"MCP did not become ready on {host}:{port} within 15s. See {log_path}",
            file=sys.stderr,
        )
        _terminate_child_process(proc)
        log_file.close()
        return 1
    finally:
        if sys.platform != "win32":
            import fcntl

            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        lock_fd.close()


def cmd_mcp(args: argparse.Namespace) -> int:
    sub = getattr(args, "mcp_sub", None)
    if sub == "install":
        return _mcp_install(args)
    if sub == "start":
        return _mcp_start_background(args)
    vault = resolve_vault(override=getattr(args, "vault", None))
    cfg = load_config(vault)
    if not (cfg.get("mcp") or {}).get("enabled", True):
        print(
            "MCP server disabled in config.json (mcp.enabled=false). Enable it to start.",
            file=sys.stderr,
        )
        return 1
    transport = getattr(args, "mcp_transport", None) or (cfg.get("mcp") or {}).get(
        "transport", "stdio"
    )
    if str(transport).lower() == "sse":
        from mcp_sse import run_sse_server

        port = getattr(args, "mcp_port", None)
        if port is None:
            port = int((cfg.get("mcp") or {}).get("port") or 8891)
        host = getattr(args, "mcp_host", None) or (cfg.get("mcp") or {}).get("host") or "127.0.0.1"
        run_sse_server(vault, port=int(port), host=str(host))
        return 0
    from mcp_server import main as mcp_main

    mcp_main()
    return 0


def _mcp_install(args: argparse.Namespace) -> int:
    """Write MCP config so Claude Code / Cursor can discover the server."""
    import json as _json
    server_path = str((plugin_root() / "scripts" / "mcp_server.py").resolve())
    vault_arg = getattr(args, "vault", None)
    entry: dict = {"command": "python3", "args": [server_path]}
    if vault_arg:
        entry["args"].extend(["--vault", str(Path(vault_arg).resolve())])

    claude_cfg = Path.home() / ".claude" / "claude_desktop_config.json"
    if claude_cfg.parent.exists():
        existing = {}
        if claude_cfg.exists():
            existing = _json.loads(claude_cfg.read_text(encoding="utf-8"))
        existing.setdefault("mcpServers", {})["llm-wiki"] = entry
        claude_cfg.write_text(_json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {claude_cfg}")

    cursor_cfg = Path.cwd() / "mcp.json"
    data = {"mcpServers": {"llm-wiki": entry}}
    cursor_cfg.write_text(_json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {cursor_cfg}")
    return 0


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
        for k, v in s.items():
            print(f"  {k}: {v}")
        return 0

    if sub == "rebuild":
        result = kg.rebuild(vault)
        print(f"Rebuilt: {result.get('added', 0)} triples added, {result.get('total_triples', 0)} total, {result.get('entities', 0)} entities")
        return 0

    print("Usage: llm-wiki kg {add|query|invalidate|timeline|stats|rebuild}", file=sys.stderr)
    return 1


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
        path = mem.memory_log_round(
            vault,
            cfg,
            sid,
            message_preview=getattr(args, "message_preview", None),
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

        out_dir = (
            Path(getattr(args, "metrics_report_out", None)).resolve()
            if getattr(args, "metrics_report_out", None)
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
    v = input(f"  MCP server — agents query wiki via 28 tools (y/n) [{'y' if mcp_cur else 'n'}]: ").strip().lower()
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="llm-wiki")
    p.add_argument("--vault", help="Path to vault directory (default: ./llm-wiki or LLM_WIKI_VAULT)")

    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("configure", help="Write config.json")
    pc.add_argument("--wiki-root")
    pc.add_argument("--og-base-url", dest="og_base_url")
    pc.add_argument("--viewer-enabled", dest="viewer_enabled", type=lambda x: x.lower() == "true")
    pc.add_argument("--git-enabled", dest="git_enabled", type=lambda x: x.lower() == "true")
    pc.add_argument("--research-enabled", dest="research_enabled", type=lambda x: x.lower() == "true")
    pc.add_argument("--security-enabled", dest="security_enabled", type=lambda x: x.lower() == "true")
    pc.add_argument("--persona-name", dest="persona_name", help="Display name for the wiki (config persona.name, default Gennie)")
    pc.add_argument("-i", "--interactive", action="store_true")
    pc.set_defaults(
        func=lambda a: cmd_interactive_configure()
        if getattr(a, "interactive", False)
        else cmd_configure(a)
    )

    ps = sub.add_parser("setup", help="Scaffold vault from templates")
    ps.add_argument("--root", default=".", help="Project root containing llm-wiki/")
    ps.add_argument("-i", "--interactive", action="store_true", help="Force step-by-step wizard even in non-TTY")
    ps.add_argument("--defaults", action="store_true", help="Skip wizard, use defaults")
    ps.set_defaults(func=cmd_setup)

    pt = sub.add_parser("teardown", help="Remove generated artifacts (or --purge vault)")
    pt.add_argument("--dry-run", action="store_true")
    pt.add_argument("--purge", action="store_true")
    pt.add_argument("--yes", action="store_true")
    pt.set_defaults(func=cmd_teardown)

    pb = sub.add_parser("build-site", help="Emit wiki-data.json + static viewer")
    pb.add_argument("--alias-build-og", action="store_true", help=argparse.SUPPRESS)
    pb.add_argument("--if-stale", action="store_true", help="Only rebuild when wiki/ is newer than wiki/.og/wiki-data.json")
    pb.set_defaults(func=cmd_build_site)
    pbo = sub.add_parser("build-og", help="Alias for build-site")
    pbo.add_argument("--if-stale", action="store_true", help="Only rebuild when wiki/ is newer than wiki/.og/wiki-data.json")
    pbo.set_defaults(func=cmd_build_site)

    pv = sub.add_parser("validate", help="Check vault layout")
    pv.add_argument("--wikilinks", action="store_true", help="Fail if wikilinks point to missing wiki pages")
    pv.set_defaults(func=cmd_validate)

    pi = sub.add_parser("ingest", help="Ingest via adapter")
    pi.add_argument("--list", action="store_true")
    pi.add_argument("--force", action="store_true", help="Ignore integrations.<id>.enabled")
    pi.add_argument("--force-security", action="store_true", help="Scan even if security disabled")
    pi.add_argument("--tags", default="", help="Comma-separated manual tags (e.g. auth,billing)")
    pi.add_argument("adapter_args", nargs=argparse.REMAINDER)
    pi.set_defaults(func=cmd_ingest)

    pdeps = sub.add_parser("deps", help="Check optional pip deps (e.g. PDF ingest)")
    pdeps.add_argument(
        "deps_cmd",
        nargs="?",
        default="check",
        choices=["check"],
        help="check: verify pdf2image/anthropic for PDF Vision ingest (default)",
    )
    pdeps.set_defaults(func=cmd_deps)

    pint = sub.add_parser("integrations", help="integrations status|validate|wizard|set-key")
    int_sub = pint.add_subparsers(dest="integrations_cmd")
    int_sub.add_parser("status", help="Show each adapter's readiness")
    int_sub.add_parser("validate", help="Exit non-zero if any adapter is misconfigured")
    int_sub.add_parser("wizard", help="Interactive setup for all integrations")
    psk = int_sub.add_parser("set-key", help="Set an API key for an adapter (saved to ~/.claude/settings.json)")
    psk.add_argument("adapter", help="Adapter id (e.g. firecrawl, perplexity, twitter, firebase)")
    psk.add_argument("key_value", help="The API key value to store")
    pint.set_defaults(func=cmd_integrations, integrations_cmd="status")

    pg = sub.add_parser("git", help="Vault-scoped git")
    pg.add_argument(
        "git_cmd",
        choices=["init", "status", "log", "diff", "snapshot", "query", "lifecycle"],
    )
    pg.add_argument("-n", type=int, default=20)
    pg.add_argument("--since")
    pg.add_argument("--grep")
    pg.add_argument("--staged", action="store_true")
    pg.add_argument("-m", "--message")
    pg.add_argument(
        "--phase",
        default=None,
        metavar="PHASE",
        help="snapshot: prepend prefix for this phase; lifecycle: filter commits to this phase",
    )
    pg.add_argument(
        "--json",
        dest="lifecycle_json",
        action="store_true",
        help="lifecycle: print JSON (hash, subject, date, author, phase)",
    )
    pg.set_defaults(func=cmd_git)

    prl = sub.add_parser(
        "research-loop",
        help="Run research tasks file (JSON default; YAML needs PyYAML; research_loop.enabled)",
    )
    prl.add_argument("--dry-run", action="store_true", help="List runnable tasks only")
    prl.add_argument("--task", metavar="ID", help="Run a single task by id")
    prl.add_argument("--force", action="store_true", help="Ignore integrations.<adapter>.enabled")
    prl.set_defaults(func=cmd_research_loop_cli)

    pgr = sub.add_parser(
        "graph",
        help="Generate D3 wiki link graph into .tmp/llm-wiki-graph (serve with http.server)",
    )
    pgr.add_argument("--mode", choices=["links", "knowledge"], default="links", help="links: degree-colored; knowledge: connected-component clusters")
    pgr.add_argument("--out", type=Path, help="Output directory (default: ./.tmp/llm-wiki-graph)")
    pgr.set_defaults(func=cmd_graph)

    pgk = sub.add_parser(
        "graph-knowledge",
        help="Alias for graph --mode knowledge (cluster pages that link into the same component)",
    )
    pgk.add_argument("--out", type=Path, help="Output directory (default: ./.tmp/llm-wiki-graph)")
    pgk.set_defaults(func=cmd_graph_knowledge)

    pwakeup = sub.add_parser("wake-up", help="Print L0+L1 context blob")
    pwakeup.add_argument(
        "--update-claude",
        action="store_true",
        help="Refresh ## Memory Stack in llm-wiki/CLAUDE.md",
    )
    pwakeup.set_defaults(func=cmd_wakeup)

    pltopics = sub.add_parser("list-topics", help="Show tag index with wiki coverage")
    pltopics.set_defaults(func=cmd_list_topics)

    psec = sub.add_parser("security", help="Security scan")
    psec_sub = psec.add_subparsers(dest="sec_cmd", required=True)
    pscan = psec_sub.add_parser("scan")
    pscan.add_argument("file")
    pscan.set_defaults(func=cmd_security)

    praw = sub.add_parser(
        "raw",
        help="Validate markdown under raw/ (deterministic) + append preparation audit log",
    )
    praw_sub = praw.add_subparsers(dest="raw_cmd", required=True)
    praw_val = praw_sub.add_parser(
        "validate",
        help="Check structural markdown issues for a file under raw/ (exit 1 if problems)",
    )
    praw_val.add_argument(
        "path",
        help="Path relative to raw/, e.g. pdfs/issue.md",
    )
    praw_val.add_argument(
        "--autofix",
        action="store_true",
        help="Apply safe deterministic fixes (line endings, trailing whitespace, final newline)",
    )
    praw_val.set_defaults(func=cmd_raw_validate)
    praw_rec = praw_sub.add_parser(
        "record",
        help="Append one JSON line to raw/.preparation-log.jsonl (audit trail after LLM cleanup)",
    )
    praw_rec.add_argument("path", help="Path relative to raw/, e.g. pdfs/issue.md")
    praw_rec.add_argument("--goal", required=True, help="What this preparation achieved")
    praw_rec.add_argument(
        "--action",
        default="noted",
        choices=["validated", "autofixed", "llm_cleaned", "noted"],
        help="Kind of preparation step",
    )
    praw_rec.add_argument("--notes", default="", help="Optional extra context")
    praw_rec.set_defaults(func=cmd_raw_record)
    praw_fin = praw_sub.add_parser(
        "finish",
        help="Autofix + validate, append preparation log, git commit with [prepare] (requires git.enabled)",
    )
    praw_fin.add_argument("path", help="Path relative to raw/, e.g. pdfs/issue.md")
    praw_fin.add_argument(
        "-m",
        "--message",
        required=True,
        help="Commit description (subject after [prepare]) and default preparation goal",
    )
    praw_fin.add_argument(
        "--goal",
        help="Override goal in raw/.preparation-log.jsonl (default: same as -m)",
    )
    praw_fin.add_argument(
        "--record-action",
        dest="record_action",
        default=None,
        choices=["validated", "autofixed", "llm_cleaned", "noted"],
        help="Log action (default: autofixed if autofix changed file, else validated)",
    )
    praw_fin.add_argument("--notes", default="", help="Optional notes in preparation log")
    praw_fin.add_argument(
        "--no-autofix",
        dest="autofix",
        action="store_false",
        help="Validate only (no deterministic autofix)",
    )
    praw_fin.add_argument(
        "--skip-git",
        action="store_true",
        help="Append preparation log only; do not commit",
    )
    praw_fin.set_defaults(func=cmd_raw_finish, autofix=True)
    praw_rebuild = praw_sub.add_parser(
        "rebuild-index",
        help="Rebuild .hashes.json and .tags.json from raw/ frontmatter",
    )
    praw_rebuild.set_defaults(func=cmd_raw_rebuild_index)

    pch = sub.add_parser(
        "check",
        help="Fast vault/plugin sanity checks (config, optional compileall); hints for smoke-test",
    )
    pch.add_argument(
        "--plugin-repo",
        action="store_true",
        help="Plugin repo: verify agent docs match docs/AGENTS.shared.md + compileall scripts/",
    )
    pch.add_argument(
        "--claude-validate",
        action="store_true",
        help="If `claude` is on PATH, run: claude plugin validate",
    )
    pch.set_defaults(func=cmd_check)

    psync = sub.add_parser(
        "sync-agent-docs",
        help="Regenerate AGENTS.md, CLAUDE.md, rules from docs/AGENTS.shared.md (plugin repo)",
    )
    psync.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if generated files differ from docs/AGENTS.shared.md (does not write)",
    )
    psync.set_defaults(func=cmd_sync_agent_docs)

    pst = sub.add_parser(
        "smoke-test",
        help="Run full pytest suite (contracts, CLI help, vault flow, adapters) from plugin root",
    )
    pst.add_argument("-v", "--verbose", action="store_true", help="pytest -v")
    pst.add_argument(
        "--network",
        action="store_true",
        help="Enable network tests (sets RUN_NETWORK_TESTS=1 for tests marked @pytest.mark.network)",
    )
    pst.add_argument(
        "--claude",
        action="store_true",
        help="Enable Claude CLI tests (sets RUN_CLAUDE_TESTS=1; e.g. claude plugin validate)",
    )
    pst.add_argument(
        "--only-contracts",
        action="store_true",
        help="Run only tests/plugin_contracts.test.py",
    )
    pst.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Extra args passed to pytest (use -- before them)",
    )
    pst.set_defaults(func=cmd_smoke_test)

    ptr = sub.add_parser(
        "test-report",
        help="Run executable CLI/doc checks and print a PASS/FAIL table (skills: frontmatter only; no LLM)",
    )
    ptr.add_argument(
        "--network",
        action="store_true",
        help="Run harvested network-requiring llm-wiki lines and probe https://example.com",
    )
    ptr.add_argument(
        "--json",
        metavar="FILE",
        help="Write machine-readable report (JSON) to FILE",
    )
    ptr.add_argument(
        "--plain",
        action="store_true",
        help="Plain text output instead of Markdown",
    )
    ptr.set_defaults(func=cmd_test_report)

    # ── MCP server ───────────────────────────────────────────────────────
    pmcp = sub.add_parser(
        "mcp",
        help="Start the MCP server (stdio JSON-RPC by default, or HTTP with --transport sse)",
    )
    pmcp.add_argument(
        "--transport",
        dest="mcp_transport",
        default=None,
        choices=("stdio", "sse"),
        help="stdio (default) or sse (HTTP POST JSON-RPC on --port)",
    )
    pmcp.add_argument(
        "--port",
        dest="mcp_port",
        type=int,
        default=None,
        help="Port for --transport sse (default: config mcp.port or 8891)",
    )
    pmcp.add_argument(
        "--host",
        dest="mcp_host",
        default=None,
        help="Bind address for --transport sse (default: config mcp.host or 127.0.0.1)",
    )
    pmcp_sub = pmcp.add_subparsers(dest="mcp_sub")
    pmcp_install = pmcp_sub.add_parser("install", help="Write MCP config for Claude Code / Cursor discovery")
    pmcp_start = pmcp_sub.add_parser(
        "start",
        help="Ensure HTTP MCP (--transport sse) is listening; start in background if needed",
    )
    pmcp_start.add_argument(
        "--port",
        dest="mcp_port",
        type=int,
        default=None,
        help="Port (default: config mcp.port or 8891)",
    )
    pmcp_start.add_argument(
        "--host",
        dest="mcp_host",
        default=None,
        help="Bind address (default: config mcp.host or 127.0.0.1)",
    )
    pmcp.set_defaults(func=cmd_mcp)

    # ── Knowledge graph ──────────────────────────────────────────────────
    pkg = sub.add_parser("kg", help="Knowledge graph: add/query/invalidate/timeline/stats/rebuild")
    pkg_sub = pkg.add_subparsers(dest="kg_sub", required=True)

    pkg_add = pkg_sub.add_parser("add", help="Add a fact triple")
    pkg_add.add_argument("subject")
    pkg_add.add_argument("predicate")
    pkg_add.add_argument("object")
    pkg_add.add_argument("--from", dest="valid_from", help="When this became true (YYYY-MM-DD)")
    pkg_add.add_argument("--source", help="Source file path")

    pkg_query = pkg_sub.add_parser("query", help="Look up an entity")
    pkg_query.add_argument("entity")
    pkg_query.add_argument("--as-of", dest="as_of", help="Point-in-time filter (YYYY-MM-DD)")

    pkg_inv = pkg_sub.add_parser("invalidate", help="Mark a fact as ended")
    pkg_inv.add_argument("subject")
    pkg_inv.add_argument("predicate")
    pkg_inv.add_argument("object")
    pkg_inv.add_argument("--ended", help="When it stopped being true (YYYY-MM-DD, default: today)")

    pkg_tl = pkg_sub.add_parser("timeline", help="Chronological entity history")
    pkg_tl.add_argument("entity", nargs="?", default=None)

    pkg_sub.add_parser("stats", help="Knowledge graph overview")
    pkg_sub.add_parser("rebuild", help="Rebuild KG from vault wikilinks + tags")
    pkg.set_defaults(func=cmd_kg)

    # ── Metrics ──────────────────────────────────────────────────────────
    pmet = sub.add_parser("metrics", help="Operational metrics: record/query/stats/clear/report/summary (.metrics.jsonl)")
    pmet_sub = pmet.add_subparsers(dest="metrics_sub", required=True)

    pmet_rec = pmet_sub.add_parser("record", help="Write one metric entry")
    pmet_rec.add_argument("key", help="Metric key (e.g. search.query_ms)")
    pmet_rec.add_argument("value", help="Metric value (number or string)")
    pmet_rec.add_argument("--meta", default=None, help='JSON metadata, e.g. \'{"query":"auth"}\'')
    pmet_rec.add_argument("--tags", default="", help="Comma-separated tags")

    pmet_query = pmet_sub.add_parser("query", help="Read/filter metric records")
    pmet_query.add_argument("--key", default=None, help="Filter by metric key")
    pmet_query.add_argument("--since", default=None, help="Filter records after this ISO date")
    pmet_query.add_argument("--limit", type=int, default=100, help="Max records to return (default 100)")
    pmet_query.add_argument("--json", dest="metrics_json", action="store_true", help="Output as JSON")

    pmet_sub.add_parser("stats", help="Summary: keys, counts, file size, date range")

    pmet_clear = pmet_sub.add_parser("clear", help="Truncate or prune old entries")
    pmet_clear.add_argument("--before", default=None, help="Remove entries before this ISO date (omit to clear all)")
    pmet_clear.add_argument("--yes", action="store_true", help="Confirm clear")

    pmet_report = pmet_sub.add_parser("report", help="Generate Chart.js HTML metrics dashboard")
    pmet_report.add_argument(
        "--since",
        dest="metrics_report_since",
        default=None,
        help="Filter records after this ISO date/time (default: last 30 days)",
    )
    pmet_report.add_argument("--key", dest="metrics_report_key", default=None, help="Filter by metric key")
    pmet_report.add_argument(
        "--out",
        dest="metrics_report_out",
        default=None,
        help="Output directory (default: .tmp/llm-wiki-metrics under cwd)",
    )

    pmet_summary = pmet_sub.add_parser("summary", help="Print metrics summary table for chat/terminal")
    pmet_summary.add_argument(
        "--since",
        dest="metrics_summary_since",
        default=None,
        help="Filter records after this ISO date/time (default: last 30 days)",
    )
    pmet_summary.add_argument("--key", dest="metrics_summary_key", default=None, help="Filter by metric key")
    pmet_summary.add_argument(
        "--json",
        dest="metrics_summary_json",
        action="store_true",
        help="Output as JSON",
    )

    pmet.set_defaults(func=cmd_metrics)

    # ── Benchmarks ───────────────────────────────────────────────────────
    pbench = sub.add_parser(
        "benchmark",
        help="Retrieval benchmarks (LME / LoCoMo / ConvoMem) and recorded metrics",
    )
    pbench_sub = pbench.add_subparsers(dest="benchmark_sub", required=True)

    pbench_sub.add_parser(
        "suites",
        help="Describe peer benchmark suites (LME, LoCoMo, ConvoMem) and example commands",
    )

    pbench_run = pbench_sub.add_parser("run", help="Run a benchmark suite")
    pbench_run.add_argument(
        "benchmark_suite",
        nargs="?",
        default="lme",
        choices=["lme", "longmemeval", "locomo", "convomem"],
        help="Suite: lme (LongMemEval), locomo, convomem (default: lme)",
    )
    pbench_run.add_argument(
        "--backend",
        dest="benchmark_backend",
        default=None,
        help="Search backend: fts5, grep, chromadb, hybrid, or all (default: config benchmark.search.backend)",
    )
    pbench_run.add_argument(
        "--compress",
        dest="benchmark_compress",
        default=None,
        help="Compressor: raw, steno, prune, extract, compact, or all (default: config benchmark.compress_method)",
    )
    pbench_run.add_argument(
        "--limit",
        dest="benchmark_limit",
        type=int,
        default=0,
        help="Max questions (0 = all)",
    )
    pbench_run.add_argument(
        "--top-k",
        dest="benchmark_top_k",
        type=int,
        default=5,
        help="Recall/NDCG cutoff for primary headline metric (default: 5)",
    )
    pbench_run.add_argument(
        "--data",
        dest="benchmark_data",
        default=None,
        help="Path to dataset JSON (LME default: download to data cache)",
    )
    pbench_run.add_argument(
        "--no-metrics",
        dest="benchmark_no_metrics",
        action="store_true",
        help="Do not append metrics to .metrics.jsonl",
    )

    pbench_report = pbench_sub.add_parser("report", help="Print benchmark metric records")
    pbench_report.add_argument(
        "--since",
        dest="benchmark_since",
        default=None,
        help="Filter records after this ISO date/time",
    )
    pbench_report.add_argument(
        "--json",
        dest="benchmark_json",
        action="store_true",
        help="Output as JSON",
    )

    pbench_hist = pbench_sub.add_parser("history", help="Benchmark metric history (recent lines)")
    pbench_hist.add_argument(
        "--limit",
        dest="benchmark_history_limit",
        type=int,
        default=30,
        help="Max benchmark lines (default: 30)",
    )

    pbench_cmp = pbench_sub.add_parser(
        "compare",
        help="Diff two LME snapshots (benchmark.lme.recall_at_5) by index into recent runs",
    )
    pbench_cmp.add_argument(
        "--a",
        dest="benchmark_compare_a",
        type=int,
        default=-2,
        help="Index into recent LME snapshots (default: -2)",
    )
    pbench_cmp.add_argument(
        "--b",
        dest="benchmark_compare_b",
        type=int,
        default=-1,
        help="Index into recent LME snapshots (default: -1)",
    )
    pbench_cmp.add_argument(
        "--json",
        dest="benchmark_compare_json",
        action="store_true",
        help="Same as default (JSON output)",
    )

    pbench_analyze = pbench_sub.add_parser(
        "analyze",
        help="Summarize lme_failures.jsonl (buckets, question ids, LLM flags)",
    )
    pbench_analyze.add_argument(
        "--suite",
        dest="benchmark_analyze_suite",
        default="lme",
        choices=["lme"],
        help="Which failure log (default: lme)",
    )
    pbench_analyze.add_argument(
        "--failures",
        dest="benchmark_failures_path",
        default=None,
        help="Path to JSONL (default: <vault>/.benchmarks/lme_failures.jsonl)",
    )
    pbench_analyze.add_argument(
        "--json",
        dest="benchmark_analyze_json",
        action="store_true",
        help="Emit full JSON (includes per-row records)",
    )

    pbench.set_defaults(func=cmd_benchmark)

    # ── Session memory ───────────────────────────────────────────────────
    pmemory = sub.add_parser("memory", help="Session memory files under raw/memory/")
    pmemory_sub = pmemory.add_subparsers(dest="memory_sub", required=True)

    msave = pmemory_sub.add_parser("save", help="Update session memory markdown")
    msave.add_argument("--session-id", "-s", dest="session_id", default=None)
    msave.add_argument("-c", "--current", action="store_true")
    msave.add_argument("--summary", default=None)
    msave.add_argument("--compact-summary", default=None)
    msave.add_argument("--tags", default=None)
    msave.add_argument("--metadata", default=None)

    mlog = pmemory_sub.add_parser("log", help="Append a round entry (typically from Stop hook)")
    mlog.add_argument("--session-id", "-s", dest="session_id", default=None)
    mlog.add_argument("-c", "--current", action="store_true")
    mlog.add_argument("--message-preview", default=None)

    mlist = pmemory_sub.add_parser("list", help="List session memory files")
    mlist.add_argument("--session-id", dest="session_filter", default=None)
    mlist.add_argument("--tag", default=None)
    mlist.add_argument("--json", dest="json_out", action="store_true")

    mshow = pmemory_sub.add_parser("show", help="Print one session memory file")
    mshow.add_argument("session_id_arg", nargs="?", default=None)
    mshow.add_argument("-c", "--current", action="store_true")

    mrec = pmemory_sub.add_parser("recall", help="Search session memories (indexed scope memory)")
    mrec.add_argument("query")
    mrec.add_argument("--session-id", dest="session_filter", default=None)
    mrec.add_argument("-c", "--current", action="store_true")
    mrec.add_argument("--tag", default=None)
    mrec.add_argument("--limit", type=int, default=5)

    mprune = pmemory_sub.add_parser("prune", help="Delete session memory files")
    mprune.add_argument("--session-id", dest="session_filter", default=None)
    mprune.add_argument("--tag", default=None)
    mprune.add_argument("--older-than", type=int, dest="older_than", default=None)
    mprune.add_argument("--keep", type=int, default=None)
    mprune.add_argument("--dry-run", action="store_true")

    pmemory.set_defaults(func=cmd_memory)

    return p


def main() -> int:
    # Repo-root .env / .env.local so ANTHROPIC_API_KEY etc. work without manual export.
    if str(os.environ.get("LLM_WIKI_SKIP_DOTENV", "")).lower() not in ("1", "true", "yes"):
        load_plugin_dotenv(plugin_root())
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
