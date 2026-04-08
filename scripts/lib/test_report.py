"""Executable integration report: CLI, vault flow, command docs, skill frontmatter — tabular output."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from lib.paths import plugin_root
from lib.sitegen import _simple_frontmatter


@dataclass
class ReportRow:
    id: str
    category: str
    name: str
    ok: bool
    ms: float
    detail: str
    skipped: bool = False


FENCE = re.compile(r"^```(?:bash|sh|zsh)?\s*$([\s\S]*?)^```", re.MULTILINE)


def _env_with_scripts(root: Path, base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base or os.environ)
    p = str(root / "scripts")
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = p if not prev else f"{p}{os.pathsep}{prev}"
    return env


def _run(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float = 120,
) -> tuple[int, str]:
    try:
        r = subprocess.run(
            argv,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        return 1, f"timeout after {timeout}s: {e}"
    except OSError as e:
        return 1, str(e)
    tail = ((r.stderr or "") + (r.stdout or ""))[-400:]
    return r.returncode, tail.strip()


def harvest_llm_wiki_lines(commands_dir: Path) -> list[tuple[str, str]]:
    """(source_file, full line) for each unique llm-wiki line in bash fences."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for path in sorted(commands_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in FENCE.finditer(text):
            block = m.group(1)
            for line in block.splitlines():
                line = line.strip()
                if line.startswith("bin/llm-wiki "):
                    line = "llm-wiki " + line[len("bin/llm-wiki ") :]
                if line.startswith("llm-wiki ") and line not in seen:
                    seen.add(line)
                    out.append((path.name, line))
    return out


def _classify_argv(argv: list[str], *, network: bool) -> tuple[str, str]:
    """
    Return (action, reason) where action is run|skip|network|rewrite_file.
    """
    if not argv:
        return "skip", "empty argv"
    a0 = argv[0]
    if a0 == "ingest" and len(argv) >= 2:
        if argv[1] == "--list":
            return "run", ""
        if argv[1] == "file":
            return "rewrite_file", ""
        if argv[1] in ("url", "hackernews", "youtube", "twitter", "perplexity", "brave"):
            return ("run", "") if network else ("network", f"ingest {argv[1]} needs --network")
    if a0 == "deps":
        return "skip", "optional PDF/Vision deps — run manually: llm-wiki deps check"
    if a0 == "integrations" and len(argv) >= 2 and argv[1] == "validate":
        return "skip", "exits 1 if any adapter lacks keys (expected in dev)"
    if a0 == "research-loop" and "--dry-run" not in argv:
        return "skip", "use research-loop --dry-run only in report"
    if a0 == "configure" and "-i" in argv:
        return "skip", "interactive configure"
    if a0 == "integrations" and len(argv) >= 2 and argv[1] == "wizard":
        return "skip", "interactive wizard"
    if a0 == "teardown" and "--purge" in argv:
        return "skip", "destructive teardown"
    if a0 in ("validate", "build-site", "build-og", "wake-up", "list-topics", "deps", "check", "graph", "graph-knowledge"):
        return "run", ""
    if a0 == "integrations" and len(argv) >= 2 and argv[1] in ("status", "validate"):
        return "run", ""
    if a0 == "git" and len(argv) >= 2 and argv[1] in ("log", "lifecycle", "query"):
        return "skip", "needs ≥1 git commit (fresh vault has none)"
    if a0 == "git" and len(argv) >= 2 and argv[1] in ("status", "diff"):
        return "run", ""
    if a0 == "security" and len(argv) >= 2 and argv[1] == "scan":
        return "skip", "needs file path"
    if a0 == "raw":
        return "skip", "raw subcommand handled in vault flow"
    if a0 == "setup":
        return "skip", "setup handled in vault flow"
    if a0 == "ingest" and argv[1] not in ("--list", "file"):
        return ("run", "") if network else ("network", "ingest adapter may need network")
    return "skip", f"not allowlisted ({a0})"


def run_test_report(
    *,
    network: bool = False,
    json_out: Path | None = None,
    markdown: bool = True,
) -> int:
    """Run integration checks; print table; return 0 iff no failures (skips OK)."""
    root = plugin_root()
    py = sys.executable
    llm = root / "scripts" / "llm_wiki.py"
    rows: list[ReportRow] = []

    # Import parser for help coverage
    if str(root / "scripts") not in sys.path:
        sys.path.insert(0, str(root / "scripts"))
    from llm_wiki import build_parser  # noqa: E402

    from lib.cli_spec import top_level_subcommands  # noqa: E402

    env0 = _env_with_scripts(root)

    # --- compileall ---
    import compileall

    t0 = time.perf_counter()
    cok = compileall.compile_dir(str(root / "scripts"), quiet=1, maxlevels=16)
    rows.append(
        ReportRow(
            "script.compileall",
            "scripts",
            "compileall scripts/",
            cok,
            (time.perf_counter() - t0) * 1000,
            "" if cok else "compileall reported failure",
        )
    )

    # --- top-level --help ---
    subs = sorted(top_level_subcommands(build_parser()))
    for sub in subs:
        t0 = time.perf_counter()
        code, detail = _run([py, str(llm), sub, "--help"], cwd=root, env=env0)
        rows.append(
            ReportRow(
                f"cli.help.{sub}",
                "cli",
                f"{sub} --help",
                code == 0,
                (time.perf_counter() - t0) * 1000,
                detail[:200] if code != 0 else "",
            )
        )

    # --- nested --help (sample) ---
    nested = [
        ["integrations", "status"],
        ["git", "status"],
        ["raw", "validate"],
        ["security", "scan"],
    ]
    for parts in nested:
        t0 = time.perf_counter()
        code, detail = _run([py, str(llm), *parts, "--help"], cwd=root, env=env0)
        rows.append(
            ReportRow(
                f"cli.help.{'_'.join(parts)}",
                "cli",
                " ".join(parts) + " --help",
                code == 0,
                (time.perf_counter() - t0) * 1000,
                detail[:200] if code != 0 else "",
            )
        )

    # --- temp vault flow ---
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "proj"
        proj.mkdir()
        vault = proj / "llm-wiki"
        env_v = _env_with_scripts(root)
        env_v["LLM_WIKI_VAULT"] = str(vault)

        steps: list[tuple[str, list[str]]] = [
            ("vault.setup", ["setup", "--root", str(proj)]),
            ("vault.validate", ["validate"]),
            ("vault.ingest_list", ["ingest", "--list"]),
            ("vault.integrations_status", ["integrations", "status"]),
            ("vault.wake_up", ["wake-up"]),
            ("vault.list_topics", ["list-topics"]),
        ]
        for rid, argv in steps:
            t0 = time.perf_counter()
            code, detail = _run([py, str(llm), *argv], cwd=root, env=env_v)
            rows.append(
                ReportRow(
                    rid,
                    "vault",
                    "llm-wiki " + " ".join(argv),
                    code == 0,
                    (time.perf_counter() - t0) * 1000,
                    detail[:200] if code != 0 else "",
                )
            )

        sample = proj / "note.md"
        sample.write_text("# Report note\n\nBody.\n", encoding="utf-8")
        t0 = time.perf_counter()
        code, detail = _run(
            [py, str(llm), "ingest", "file", str(sample), "--out", "report-note.md"],
            cwd=root,
            env=env_v,
        )
        rows.append(
            ReportRow(
                "vault.ingest_file",
                "vault",
                "ingest file … --out report-note.md",
                code == 0,
                (time.perf_counter() - t0) * 1000,
                detail[:200] if code != 0 else "",
            )
        )
        if code == 0:
            t0 = time.perf_counter()
            code, detail = _run([py, str(llm), "raw", "validate", "report-note.md"], cwd=root, env=env_v)
            rows.append(
                ReportRow(
                    "vault.raw_validate",
                    "vault",
                    "raw validate report-note.md",
                    code == 0,
                    (time.perf_counter() - t0) * 1000,
                    detail[:200] if code != 0 else "",
                )
            )
        (vault / "wiki" / "report.md").write_text("# R\n\n[[index]]\n", encoding="utf-8")
        t0 = time.perf_counter()
        code, detail = _run([py, str(llm), "build-site"], cwd=root, env=env_v)
        rows.append(
            ReportRow(
                "vault.build_site",
                "vault",
                "build-site",
                code == 0,
                (time.perf_counter() - t0) * 1000,
                detail[:200] if code != 0 else "",
            )
        )
        t0 = time.perf_counter()
        code, detail = _run([py, str(llm), "validate", "--wikilinks"], cwd=root, env=env_v)
        rows.append(
            ReportRow(
                "vault.validate_wikilinks",
                "vault",
                "validate --wikilinks",
                code == 0,
                (time.perf_counter() - t0) * 1000,
                detail[:200] if code != 0 else "",
            )
        )
        gout = Path(td) / "graph-out"
        t0 = time.perf_counter()
        code, detail = _run([py, str(llm), "graph", "--out", str(gout)], cwd=root, env=env_v)
        rows.append(
            ReportRow(
                "vault.graph",
                "vault",
                "graph --out <tmp>",
                code == 0,
                (time.perf_counter() - t0) * 1000,
                detail[:200] if code != 0 else "",
            )
        )
        t0 = time.perf_counter()
        code, detail = _run([py, str(llm), "git", "status"], cwd=root, env=env_v)
        rows.append(
            ReportRow(
                "vault.git_status",
                "vault",
                "git status",
                code == 0,
                (time.perf_counter() - t0) * 1000,
                detail[:200] if code != 0 else "",
            )
        )

        t0 = time.perf_counter()
        code, detail = _run(
            [py, str(llm), "research-loop", "--dry-run"],
            cwd=root,
            env=env_v,
        )
        rows.append(
            ReportRow(
                "vault.research_loop_dry",
                "vault",
                "research-loop --dry-run",
                code == 0,
                (time.perf_counter() - t0) * 1000,
                detail[:200] if code != 0 else "",
            )
        )

        # --- harvested command docs ---
        for fname, line in harvest_llm_wiki_lines(root / "commands"):
            raw = line[len("llm-wiki ") :].strip() if line.startswith("llm-wiki ") else line
            try:
                argv = shlex.split(raw)
            except ValueError as e:
                rows.append(
                    ReportRow(
                        f"cmd.{fname}.parse",
                        "command_doc",
                        line[:80],
                        False,
                        0,
                        str(e),
                    )
                )
                continue
            action, reason = _classify_argv(argv, network=network)
            rid = f"cmd.{fname}:{line[:48]}"
            if action == "skip":
                rows.append(
                    ReportRow(rid, "command_doc", line[:100], True, 0, reason, skipped=True)
                )
                continue
            if action == "network":
                rows.append(
                    ReportRow(rid, "command_doc", line[:100], True, 0, reason, skipped=True)
                )
                continue
            run_argv = list(argv)
            if action == "rewrite_file":
                run_argv = ["ingest", "file", str(sample), "--out", "harvest-copy.md"]
            t0 = time.perf_counter()
            code, detail = _run([py, str(llm), *run_argv], cwd=root, env=env_v)
            rows.append(
                ReportRow(
                    rid,
                    "command_doc",
                    line[:100],
                    code == 0,
                    (time.perf_counter() - t0) * 1000,
                    detail[:200] if code != 0 else "",
                )
            )

    # --- skills: frontmatter ---
    for skill_md in sorted((root / "skills").glob("*/SKILL.md")):
        t0 = time.perf_counter()
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        fm, _ = _simple_frontmatter(text)
        ok = bool(fm.get("name") and fm.get("description"))
        sid = skill_md.parent.name
        rows.append(
            ReportRow(
                f"skill.{sid}.frontmatter",
                "skill",
                sid,
                ok,
                (time.perf_counter() - t0) * 1000,
                "" if ok else "missing name/description",
            )
        )

    # --- optional network ---
    if network:
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request("https://example.com", headers={"User-Agent": "llm-wiki-test-report"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                ok = resp.status == 200
            detail = ""
        except (urllib.error.URLError, OSError) as e:
            ok = False
            detail = str(e)[:200]
        rows.append(
            ReportRow(
                "network.example_com",
                "network",
                "GET https://example.com",
                ok,
                (time.perf_counter() - t0) * 1000,
                detail,
            )
        )

    # --- optional claude validate ---
    claude = shutil.which("claude")
    if claude:
        t0 = time.perf_counter()
        code, detail = _run([claude, "plugin", "validate", str(root)], cwd=root, env=env0)
        rows.append(
            ReportRow(
                "claude.plugin_validate",
                "claude",
                "claude plugin validate <repo>",
                code == 0,
                (time.perf_counter() - t0) * 1000,
                detail[:200] if code != 0 else "",
            )
        )
    else:
        rows.append(
            ReportRow(
                "claude.plugin_validate",
                "claude",
                "claude plugin validate",
                True,
                0,
                "claude not on PATH",
                skipped=True,
            )
        )

    # --- output ---
    failed = sum(1 for r in rows if not r.ok and not r.skipped)
    skipped = sum(1 for r in rows if r.skipped)
    passed = sum(1 for r in rows if r.ok and not r.skipped)
    summary = {"passed": passed, "failed": failed, "skipped": skipped, "total": len(rows)}

    if markdown:
        print("# llm-wiki test report\n")
        print("| Result | ID | Category | Name | ms | Detail |")
        print("|--------|-----|----------|------|-----|--------|")
        for r in rows:
            mark = "SKIP" if r.skipped else ("PASS" if r.ok else "FAIL")
            name = (r.name or r.id)[:60].replace("|", "\\|")
            det = (r.detail or "")[:80].replace("|", "\\|")
            print(f"| {mark} | `{r.id}` | {r.category} | {name} | {r.ms:.1f} | {det} |")
        print()
        print(f"**Summary:** {passed} passed, {failed} failed, {skipped} skipped, {len(rows)} rows.")
    else:
        w = max(len(r.id) for r in rows) if rows else 10
        for r in rows:
            st = "SKIP" if r.skipped else ("ok" if r.ok else "NO")
            print(f"{st:4} {r.category:12} {r.id:{w}} {r.ms:8.1f}ms  {r.detail}")
        print(f"\n{passed} passed, {failed} failed, {skipped} skipped")

    if json_out:
        payload = {"summary": summary, "rows": [asdict(r) for r in rows]}
        json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nWrote JSON → {json_out}", file=sys.stderr)

    return 1 if failed else 0


def cmd_test_report(args) -> int:
    json_path = Path(args.json) if getattr(args, "json", None) else None
    return run_test_report(
        network=getattr(args, "network", False),
        json_out=json_path,
        markdown=not getattr(args, "plain", False),
    )
