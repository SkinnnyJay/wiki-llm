"""Argparse definition for the llm-wiki CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.self_check import cmd_check, cmd_smoke_test
from lib.test_report import cmd_test_report
from lib.version import __version__

from cli.core_commands import (
    cmd_build_site,
    cmd_compile,
    cmd_configure,
    cmd_deps,
    cmd_diff,
    cmd_git,
    cmd_graph,
    cmd_graph_knowledge,
    cmd_ingest,
    cmd_integrations,
    cmd_knowledge_test,
    cmd_lint,
    cmd_list_topics,
    cmd_raw_finish,
    cmd_raw_record,
    cmd_raw_rebuild_index,
    cmd_raw_validate,
    cmd_research_loop_cli,
    cmd_security,
    cmd_search,
    cmd_setup,
    cmd_sync_agent_docs,
    cmd_teardown,
    cmd_validate,
    cmd_wakeup,
)
from cli.mcp_commands import cmd_mcp
from cli.doctor_commands import cmd_doctor
from cli.ops_commands import (
    cmd_benchmark,
    cmd_interactive_configure,
    cmd_kg,
    cmd_memory,
    cmd_metrics,
)


def _add_build_site_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument(
        "--if-stale",
        action="store_true",
        help="Only rebuild when wiki/ is newer than wiki/.og/wiki-data.json",
    )
    ap.add_argument(
        "--serve",
        action="store_true",
        help="After build, serve wiki/.og over HTTP (blocking; Ctrl+C stops)",
    )
    ap.add_argument(
        "--serve-background",
        action="store_true",
        help="After build, start HTTP server in background (prints URL and PID)",
    )
    ap.add_argument(
        "--open",
        action="store_true",
        help="Open the viewer URL after starting --serve or --serve-background",
    )
    ap.add_argument(
        "--port",
        type=int,
        default=None,
        metavar="PORT",
        help="Port for --serve / --serve-background (default: viewer.port in config, else 8765)",
    )
    ap.add_argument(
        "--stop-serving",
        action="store_true",
        help="Stop background HTTP server started with --serve-background (wiki/.og/.viewer-http.pid)",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="llm-wiki")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--vault", help="Path to vault directory (default: ./llm-wiki or LLM_WIKI_VAULT)")

    sub = p.add_subparsers(dest="cmd", required=False)

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
    ps.add_argument(
        "--vault",
        metavar="PATH",
        help="Vault directory (default: <root>/llm-wiki). Same as: llm-wiki --vault PATH setup …",
    )
    ps.add_argument("-i", "--interactive", action="store_true", help="Force step-by-step wizard even in non-TTY")
    ps.add_argument("--defaults", action="store_true", help="Skip wizard, use defaults")
    ps.set_defaults(func=cmd_setup)

    pt = sub.add_parser("teardown", help="Remove generated artifacts (or --purge vault)")
    pt.add_argument("--dry-run", action="store_true")
    pt.add_argument("--purge", action="store_true")
    pt.add_argument("--artifacts", action="store_true", help="Remove generated indexes without deleting raw/ or wiki/")
    pt.add_argument("--yes", action="store_true")
    pt.set_defaults(func=cmd_teardown)

    pb = sub.add_parser("build-site", help="Emit wiki-data.json + static viewer")
    pb.add_argument("--alias-build-og", action="store_true", help=argparse.SUPPRESS)
    _add_build_site_args(pb)
    pb.set_defaults(func=cmd_build_site)
    pbo = sub.add_parser("build-og", help="Alias for build-site")
    _add_build_site_args(pbo)
    pbo.set_defaults(func=cmd_build_site)

    pv = sub.add_parser("validate", help="Check vault layout")
    pv.add_argument("--wikilinks", action="store_true", help="Fail if wikilinks point to missing wiki pages")
    pv.add_argument(
        "--schema",
        action="store_true",
        help="Enforce wiki frontmatter provenance schema (sources/confidence/…)",
    )
    pv.set_defaults(func=cmd_validate)

    plint = sub.add_parser("lint", help="Deterministic wiki health (orphans, links, schema, stale)")
    plint.add_argument("--schema", action="store_true", help="Require provenance frontmatter")
    plint.add_argument("--no-stale", action="store_true", help="Skip stale_after checks")
    plint.add_argument("--no-outputs", action="store_true", help="Skip outputs/ vs wiki overlap")
    plint.add_argument("--json", dest="json_out", action="store_true", help="JSON report")
    plint.add_argument(
        "--write-report",
        action="store_true",
        help="Write outputs/lint-report.json",
    )
    plint.set_defaults(func=cmd_lint)

    pdiff = sub.add_parser("diff", help="Knowledge diff: wiki/.kg changes since a git ref")
    pdiff.add_argument("--since", default="HEAD~1", help="Git ref (default: HEAD~1)")
    pdiff.add_argument("--json", dest="json_out", action="store_true")
    pdiff.add_argument("--write-report", action="store_true", help="Write outputs/knowledge-diff.json")
    pdiff.set_defaults(func=cmd_diff)

    pcomp = sub.add_parser(
        "compile",
        help="Run knowledge CI gates (validate+lint+KG conflicts+optional site)",
    )
    pcomp.add_argument("--schema", action="store_true", help="Strict provenance schema")
    pcomp.add_argument("--no-kg", action="store_true", help="Skip KG rebuild/conflicts")
    pcomp.add_argument("--no-site", action="store_true", help="Skip viewer rebuild")
    pcomp.add_argument(
        "--raw",
        default="",
        help="Surgical recompile: lint/claims for wiki pages citing this raw/ path",
    )
    pcomp.add_argument(
        "--stubs",
        action="store_true",
        help="Write draft claim stubs under outputs/stubs/ (never wiki/)",
    )
    pcomp.add_argument("--json", dest="json_out", action="store_true")
    pcomp.set_defaults(func=cmd_compile)

    pkt = sub.add_parser(
        "knowledge-test",
        help="Run knowledge regression tests (wiki claim contains/absent)",
    )
    pkt.add_argument(
        "--file",
        default="",
        help="JSON tests file (default: vault knowledge-tests.json or examples/)",
    )
    pkt.add_argument("--json", dest="json_out", action="store_true")
    pkt.set_defaults(func=cmd_knowledge_test)

    pdoctor = sub.add_parser("doctor", help="Diagnose vault health; --fix applies safe repairs only")
    pdoctor.add_argument(
        "--fix",
        action="store_true",
        help="Create missing vault/raw/wiki directories, add missing config defaults, and repair safe blank values",
    )
    pdoctor.set_defaults(func=cmd_doctor)

    psearch = sub.add_parser("search", help="Search vault content")
    psearch.add_argument("query")
    psearch.add_argument("--limit", type=int, default=5, help="Maximum results (default: 5)")
    psearch.add_argument("--tag", default="", help="Filter by tag")
    psearch.add_argument(
        "--scope",
        default="all",
        choices=["all", "wiki", "raw", "memory"],
        help="Content scope (default: all)",
    )
    psearch.set_defaults(func=cmd_search)

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
        help="Run full pytest suite (contracts, CLI help, vault flow, E2E, hooks, MCP stdio, golden replay, adapters) from plugin root",
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
        "--browser",
        action="store_true",
        help="Enable Playwright viewer smoke tests (sets RUN_BROWSER_TESTS=1; @pytest.mark.browser)",
    )
    pst.add_argument(
        "--only-contracts",
        action="store_true",
        help="Run only tests/plugin_contracts.test.py",
    )
    pst.add_argument(
        "--replay",
        action="store_true",
        help="Run only golden replay tests (tests marked @pytest.mark.replay)",
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
    pmcp_install.add_argument(
        "--project",
        type=Path,
        help="Write Cursor config under this project instead of the plugin root (requires --force)",
    )
    pmcp_install.add_argument(
        "--force",
        action="store_true",
        help="Allow replacing an existing llm-wiki Cursor MCP entry",
    )
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
    pkg = sub.add_parser("kg", help="Knowledge graph: add/query/invalidate/timeline/stats/rebuild/conflicts")
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
    pkg_query.add_argument("--json", dest="json_out", action="store_true", help="Output as JSON")

    pkg_inv = pkg_sub.add_parser("invalidate", help="Mark a fact as ended")
    pkg_inv.add_argument("subject")
    pkg_inv.add_argument("predicate")
    pkg_inv.add_argument("object")
    pkg_inv.add_argument("--ended", help="When it stopped being true (YYYY-MM-DD, default: today)")

    pkg_tl = pkg_sub.add_parser("timeline", help="Chronological entity history")
    pkg_tl.add_argument("entity", nargs="?", default=None)

    pkg_stats = pkg_sub.add_parser("stats", help="Knowledge graph overview")
    pkg_stats.add_argument("--json", dest="json_out", action="store_true", help="Output as JSON")
    pkg_sub.add_parser("rebuild", help="Rebuild KG from vault wikilinks + tags")
    pkg_conf = pkg_sub.add_parser(
        "conflicts",
        help="List active (subject,predicate) pairs with multiple objects",
    )
    pkg_conf.add_argument("--json", dest="json_out", action="store_true")
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
    pbench_run.add_argument(
        "--peer",
        dest="benchmark_peer",
        action="append",
        default=None,
        help=(
            "Optional peer memory backend (mem0, mempalace, claude-mem, supermemory); "
            "repeat for multiple. Uses the same LongMemEval JSON as vault LME; "
            "installs/cache under benchmark.peers.cache_dir (not tracked in git)."
        ),
    )
    pbench_run.add_argument(
        "--strict-peers",
        dest="benchmark_strict_peers",
        action="store_true",
        help="Fail if any selected peer cannot run or throws during LME (also benchmark.peers.strict).",
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
    mlog.add_argument("--message-preview", default=None, help="Inline preview (avoid for multiline; use --message-preview-file from hooks)")
    mlog.add_argument(
        "--message-preview-file",
        metavar="PATH",
        default=None,
        help="Read preview from file (UTF-8); preferred from shell hooks — avoids quoting bugs",
    )

    mlist = pmemory_sub.add_parser("list", help="List session memory files")
    mlist.add_argument("--session-id", dest="session_filter", default=None)
    mlist.add_argument("--tag", default=None)
    mlist.add_argument("--json", dest="json_out", action="store_true")

    mshow = pmemory_sub.add_parser("show", help="Print one session memory file")
    mshow.add_argument("session_id_arg", nargs="?", default=None)
    mshow.add_argument("-c", "--current", action="store_true")
    mshow.add_argument("--json", dest="json_out", action="store_true", help="Output as JSON")

    mrec = pmemory_sub.add_parser("recall", help="Search session memories (indexed scope memory)")
    mrec.add_argument("query")
    mrec.add_argument("--session-id", dest="session_filter", default=None)
    mrec.add_argument("-c", "--current", action="store_true")
    mrec.add_argument("--tag", default=None)
    mrec.add_argument("--limit", type=int, default=5)
    mrec.add_argument("--json", dest="json_out", action="store_true", help="Output as JSON")

    mprune = pmemory_sub.add_parser("prune", help="Delete session memory files")
    mprune.add_argument("--session-id", dest="session_filter", default=None)
    mprune.add_argument("--tag", default=None)
    mprune.add_argument("--older-than", type=int, dest="older_than", default=None)
    mprune.add_argument("--keep", type=int, default=None)
    mprune.add_argument("--dry-run", action="store_true")

    pmemory.set_defaults(func=cmd_memory)

    return p
