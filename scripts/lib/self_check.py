"""`llm-wiki check` and `llm-wiki smoke-test` — plugin health without an LLM."""

from __future__ import annotations

import compileall
import os
import shutil
import subprocess
import sys
from pathlib import Path

from lib.config_loader import load_config
from lib.paths import plugin_root, resolve_vault


def cmd_check(args) -> int:
    """
    Fast deterministic checks: vault config readable, optional plugin-repo compileall.
    Always prints pointers to smoke-test and per-command ## Smoke check sections.
    """
    vault = resolve_vault(override=getattr(args, "vault", None))
    errs = 0
    cfg_path = vault / "config.json"
    if cfg_path.is_file():
        try:
            load_config(vault)
        except Exception as e:
            print(f"config error ({cfg_path}): {e}", file=sys.stderr)
            errs += 1
    else:
        print(f"Note: no config at {cfg_path} — run: llm-wiki setup", file=sys.stderr)

    if getattr(args, "plugin_repo", False):
        root = plugin_root()
        scripts = root / "scripts"
        if scripts.is_dir():
            ok = compileall.compile_dir(str(scripts), quiet=1, maxlevels=16)
            if not ok:
                print("compileall reported failures under scripts/", file=sys.stderr)
                errs += 1
        else:
            print(f"Missing scripts dir: {scripts}", file=sys.stderr)
            errs += 1

    claude = shutil.which("claude")
    if claude and getattr(args, "claude_validate", False):
        root = plugin_root()
        r = subprocess.run(
            [claude, "plugin", "validate", str(root)],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            print(r.stdout or "", end="")
            print(r.stderr or "", end="", file=sys.stderr)
            errs += 1
        else:
            print("claude plugin validate: OK")

    print()
    print("Next steps:")
    print("  llm-wiki smoke-test              # full pytest (offline by default)")
    print("  llm-wiki smoke-test --network    # also run network reachability tests")
    print("  llm-wiki smoke-test --claude      # also run `claude plugin validate`")
    print("  llm-wiki test-report             # executable CLI + vault + doc harvest (PASS/FAIL table)")
    print("  Each commands/*.md and skills/*/SKILL.md has a ## Smoke check section (CLI + agent prompt).")
    return 1 if errs else 0


def cmd_smoke_test(args) -> int:
    """Run pytest (and thus contract + CLI + vault tests) from plugin root."""
    root = plugin_root()
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        print(f"Missing tests directory: {tests_dir}", file=sys.stderr)
        return 1

    cmd: list[str] = [sys.executable, "-m", "pytest"]
    if getattr(args, "only_contracts", False):
        cmd.append(str(tests_dir / "plugin_contracts.test.py"))
    else:
        cmd.append(str(tests_dir))
    if getattr(args, "verbose", False):
        cmd.append("-v")
    extra = list(getattr(args, "pytest_args", None) or [])
    if extra and extra[0] == "--":
        extra = extra[1:]
    cmd.extend(extra)

    env = os.environ.copy()
    if getattr(args, "network", False):
        env["RUN_NETWORK_TESTS"] = "1"
    if getattr(args, "claude", False):
        env["RUN_CLAUDE_TESTS"] = "1"
    pscripts = str(root / "scripts")
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = pscripts if not prev else f"{pscripts}{os.pathsep}{prev}"

    print("Running:", " ".join(cmd), file=sys.stderr)
    return subprocess.call(cmd, cwd=str(root), env=env)
