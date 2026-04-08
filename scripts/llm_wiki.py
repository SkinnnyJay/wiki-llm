#!/usr/bin/env python3
"""llm-wiki CLI — Claude Code LLM Wiki plugin."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.config_loader import DEFAULTS, load_config, save_config
from lib.paths import plugin_root, resolve_vault
from lib import git as vgit
from lib.sitegen import build_site, collect_wiki
from lib.graphgen import build_graph_bundle
from lib.ingest_finish import post_ingest
from lib.raw_markdown import append_preparation_log, autofix_raw_markdown, raw_file_path, validate_raw_markdown
from lib.research_loop import run_research_loop
from ingest.registry import adapter_map, run_ingest
from ingest import security as secscan


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
    if cfg.get("git", {}).get("init_on_setup"):
        try:
            print(vgit.git_init(vault, cfg))
        except vgit.GitDisabledError:
            pass
    print(f"Scaffolded vault at {vault}")
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
    cfg = load_config(vault)
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

    if sub == "status":
        for cls in adapter_map().values():
            slice_ = (cfg.get("integrations") or {}).get(cls.id) or {}
            en = slice_.get("enabled", True) if cls.id in (cfg.get("integrations") or {}) else True
            warns = cls.setup_checks(slice_)
            w = "; ".join(warns) if warns else "ok"
            print(f"{cls.id:14} enabled={str(en):<5}  {w}")
        return 0

    if sub == "validate":
        bad = False
        for cls in adapter_map().values():
            slice_ = (cfg.get("integrations") or {}).get(cls.id) or {}
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
            slice_ = (cfg.get("integrations") or {}).get(cls.id) or {}
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


def cmd_interactive_configure() -> int:
    vault = resolve_vault()
    cfg = load_config(vault)
    print("llm-wiki configure (interactive) — enter empty to keep current")
    print("Vault:", vault)
    og = input(f"viewer.og_base_url [{cfg.get('viewer', {}).get('og_base_url', '')}]: ").strip()
    if og:
        cfg.setdefault("viewer", {})["og_base_url"] = og
    cur_name = (cfg.get("persona") or {}).get("name") or DEFAULTS.get("persona", {}).get("name", "Gennie")
    pn = input(f"persona.name (wiki display name) [{cur_name}]: ").strip()
    if pn:
        cfg.setdefault("persona", {})["name"] = pn
    for key, label in [
        ("viewer", "Enable static viewer"),
        ("git", "Enable vault git"),
        ("research_loop", "Enable research loop skill"),
        ("ingestion_security", "Enable ingestion security scan"),
    ]:
        cur = cfg.get(key, {}).get("enabled", DEFAULTS.get(key, {}).get("enabled"))
        v = input(f"{label} (y/n) [{ 'y' if cur else 'n' }]: ").strip().lower()
        if v in ("y", "n"):
            cfg.setdefault(key, {})["enabled"] = v == "y"
    save_config(vault, cfg)
    print("Saved.")
    return 0


def main() -> int:
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
    ps.set_defaults(func=cmd_setup)

    pt = sub.add_parser("teardown", help="Remove generated artifacts (or --purge vault)")
    pt.add_argument("--dry-run", action="store_true")
    pt.add_argument("--purge", action="store_true")
    pt.add_argument("--yes", action="store_true")
    pt.set_defaults(func=cmd_teardown)

    pb = sub.add_parser("build-site", help="Emit wiki-data.json + static viewer")
    pb.add_argument("--alias-build-og", action="store_true", help=argparse.SUPPRESS)
    pb.set_defaults(func=cmd_build_site)
    sub.add_parser("build-og", help="Alias for build-site").set_defaults(func=cmd_build_site)

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
        help="check: verify MarkItDown/PyMuPDF for ingest pdf (default)",
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

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
