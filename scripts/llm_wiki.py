#!/usr/bin/env python3
"""llm-wiki CLI — Claude Code LLM Wiki plugin."""

from __future__ import annotations

import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Stable entrypoints for tests and tools (see tests/plugin_contracts.test.py, test_session_memory.py).
from cli.core_commands import cmd_raw_validate
from cli.parser import build_parser
from lib.env_loader import load_plugin_dotenv
from lib.paths import plugin_root
from lib.version import __version__

__all__ = ["__version__", "build_parser", "cmd_raw_validate", "main"]


def main() -> int:
    # Repo-root .env / .env.local so ANTHROPIC_API_KEY etc. work without manual export.
    if str(os.environ.get("LLM_WIKI_SKIP_DOTENV", "")).lower() not in ("1", "true", "yes"):
        load_plugin_dotenv(plugin_root())
    parser = build_parser()
    args = parser.parse_args()
    # No subcommand: common when `bin/llm-wiki` is on PATH (e.g. Claude plugin) and something probes bare `llm-wiki`.
    if getattr(args, "cmd", None) is None:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
