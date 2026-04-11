#!/usr/bin/env python3
"""Record Claude Code CLI runs as stream-json for golden fixture extraction.

Usage (from plugin repo root):
  python3 scripts/qa_record.py --scenario cli-smoke
  python3 scripts/qa_record.py --all

Requires: claude on PATH and a working Claude Code login (subscription/OAuth by default; API keys
stripped from the subprocess env unless --bare or --keep-anthropic-env). Writes to tests/fixtures/recordings/ (gitignored).
Next: python3 scripts/qa_extract_fixture.py tests/fixtures/recordings/<file>.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from lib.claude_env import strip_anthropic_api_credentials

RECORDINGS = REPO / "tests" / "fixtures" / "recordings"
BIN_LLM_WIKI = REPO / "bin" / "llm-wiki"

RECORD_SCENARIOS = [
    {
        "name": "setup-defaults",
        "prompt": (
            "Run the shell command to scaffold a vault with defaults only. Use:\n"
            "  cd {proj} && {llm_wiki} setup --defaults\n"
            "where {proj} is the empty project directory provided. Do not ask questions. "
            "Print the last few lines of stdout."
        ),
        "budget": "1.00",
        "timeout": 180,
        "fresh_project": True,
    },
    {
        "name": "cli-smoke",
        "prompt": (
            "Run: llm-wiki validate && llm-wiki list-topics\n"
            "from the vault root (bash). Show stdout."
        ),
        "budget": "0.50",
        "timeout": 120,
        "fresh_project": False,
    },
    {
        "name": "query-auth",
        "prompt": (
            "Using Read/Grep only on the vault wiki/, answer in one sentence: "
            "what do we know about authentication? Cite a wiki path."
        ),
        "budget": "0.50",
        "timeout": 120,
        "fresh_project": False,
    },
    {
        "name": "status-check",
        "prompt": "Run: llm-wiki integrations status\nReport the output briefly.",
        "budget": "0.50",
        "timeout": 120,
        "fresh_project": False,
    },
    {
        "name": "full-pipeline",
        "prompt": (
            "Run: llm-wiki validate && llm-wiki build-site\nReport OK or errors."
        ),
        "budget": "2.00",
        "timeout": 300,
        "fresh_project": False,
    },
]


def _seed_vault(parent: Path) -> Path:
    vault = parent / "llm-wiki"
    vault.mkdir(parents=True)
    (vault / "wiki").mkdir()
    (vault / "raw").mkdir()
    cfg = {
        "version": 1,
        "persona": {"name": "RecordBot"},
        "viewer": {"enabled": True},
        "git": {"enabled": False},
        "mcp": {"enabled": True, "search_backend": "fts5"},
        "knowledge_graph": {"enabled": True, "backend": "json"},
        "memory": {"enabled": False},
        "integrations": {},
        "storage": {},
    }
    (vault / "config.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    (vault / "CLAUDE.md").write_text("# V\n", encoding="utf-8")
    (vault / "wiki" / "index.md").write_text("# Index\n", encoding="utf-8")
    (vault / "wiki" / "log.md").write_text("# Log\n", encoding="utf-8")
    (vault / "wiki" / "auth.md").write_text("# Auth\nOAuth.\n", encoding="utf-8")
    return vault


def _run_claude(
    *,
    prompt: str,
    vault: Path | None,
    budget: str,
    timeout: int,
    output_path: Path,
    bare: bool,
    no_max_budget: bool,
    keep_anthropic_env: bool,
) -> int:
    claude = shutil.which("claude")
    if not claude:
        print("claude CLI not on PATH", file=sys.stderr)
        return 1
    RECORDINGS.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    p = str(SCRIPT_DIR)
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = p if not prev else f"{p}{os.pathsep}{prev}"
    if vault is not None:
        env["LLM_WIKI_VAULT"] = str(vault)
    if not bare and not keep_anthropic_env:
        env = strip_anthropic_api_credentials(env)

    cmd = [claude, "-p"]
    if bare:
        cmd.append("--bare")
    else:
        # Match tests/conftest claude_runner: avoid merging ~/.claude/settings.json env (API key).
        ss = os.environ.get("CLAUDE_RUNNER_SETTING_SOURCES", "project").strip()
        if ss:
            cmd.extend(["--setting-sources", ss])
    cmd.extend(
        [
            "--no-session-persistence",
            "--dangerously-skip-permissions",
        ]
    )
    if not no_max_budget:
        cmd.extend(["--max-budget-usd", budget])
    cmd.extend(
        [
            "--verbose",
            "--output-format",
            "stream-json",
            "--include-hook-events",
        ]
    )
    cmd.extend(["--plugin-dir", str(REPO)])
    if vault is not None:
        cmd.extend(["--add-dir", str(vault)])
    cmd.extend(["--", prompt])
    print("Recording to", output_path, file=sys.stderr)
    with open(output_path, "w", encoding="utf-8") as f:
        r = subprocess.run(
            cmd,
            cwd=str(REPO),
            env=env,
            stdout=f,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        return r.returncode
    print(f"Wrote {output_path}", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Record Claude -p stream-json for QA fixtures")
    ap.add_argument("--scenario", metavar="NAME", help="Scenario name")
    ap.add_argument("--all", action="store_true", help="Run every scenario")
    ap.add_argument(
        "--bare",
        action="store_true",
        help="Pass --bare to claude (API key only; disables OAuth/keychain — not for subscription auth)",
    )
    ap.add_argument(
        "--no-max-budget",
        action="store_true",
        help="Omit --max-budget-usd (use with Claude Code subscription; flag caps API spend)",
    )
    ap.add_argument(
        "--keep-anthropic-env",
        action="store_true",
        help="Pass ANTHROPIC_API_KEY through (default: strip for subscription/OAuth CLI login)",
    )
    args = ap.parse_args()
    if not args.scenario and not args.all:
        ap.print_help()
        print("\nScenarios:", ", ".join(s["name"] for s in RECORD_SCENARIOS), file=sys.stderr)
        return 1

    scenarios = RECORD_SCENARIOS if args.all else [s for s in RECORD_SCENARIOS if s["name"] == args.scenario]
    if not scenarios:
        print(f"Unknown scenario: {args.scenario}", file=sys.stderr)
        return 1

    llm = str(BIN_LLM_WIKI) if BIN_LLM_WIKI.is_file() else "llm-wiki"
    rc = 0
    for sc in scenarios:
        name = sc["name"]
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = RECORDINGS / f"{name}-{ts}.jsonl"
        with tempfile.TemporaryDirectory(prefix="qa-record-") as td:
            base = Path(td)
            if sc.get("fresh_project"):
                proj = base / "proj"
                proj.mkdir()
                prompt = sc["prompt"].format(proj=str(proj), llm_wiki=llm)
                vault_path: Path | None = None
            else:
                v = _seed_vault(base)
                prompt = sc["prompt"]
                vault_path = v
            r = _run_claude(
                prompt=prompt,
                vault=vault_path,
                budget=sc["budget"],
                timeout=int(sc["timeout"]),
                output_path=out,
                bare=args.bare,
                no_max_budget=args.no_max_budget,
                keep_anthropic_env=args.keep_anthropic_env,
            )
            if r != 0:
                rc = r
    return rc


if __name__ == "__main__":
    sys.exit(main())
