#!/usr/bin/env python3
"""Extract a golden replay JSON fixture from a Claude stream-json recording (JSONL).

Usage:
  python3 scripts/qa_extract_fixture.py tests/fixtures/recordings/cli-smoke-*.jsonl \\
    -o tests/fixtures/golden/cli-smoke.json

Heuristic: collects Bash tool commands and simple file existence hints from tool results.
Review and edit the output before committing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _looks_like_llm_wiki_bash(cmd: str) -> bool:
    s = cmd.strip()
    if "llm-wiki" in s or "llm_wiki.py" in s:
        return True
    if re.search(r"python3?\s+.*llm_wiki\.py", s):
        return True
    return False


def _split_llm_wiki_argv(cmd: str) -> list[str] | None:
    """If cmd is a simple `llm-wiki sub ...` or `python ... llm_wiki.py sub ...`, return argv after script."""
    s = cmd.strip()
    # Strip common wrappers
    if s.startswith("cd ") and "&&" in s:
        parts = s.split("&&")
        s = parts[-1].strip()
    m = re.match(r"^(?:[^\s]+\/)?llm-wiki\s+(.+)$", s)
    if m:
        rest = m.group(1)
        return _shell_split(rest)
    m2 = re.search(r"llm_wiki\.py\s+(.+)$", s)
    if m2:
        return _shell_split(m2.group(1))
    return None


def _shell_split(line: str) -> list[str]:
    """Very small splitter for typical llm-wiki args (no nested quotes)."""
    out: list[str] = []
    cur = []
    in_q: str | None = None
    for ch in line:
        if in_q:
            if ch == in_q:
                in_q = None
            else:
                cur.append(ch)
        elif ch in "'\"":
            in_q = ch
        elif ch.isspace():
            if cur:
                out.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur))
    return out


def extract_from_recording(path: Path) -> dict:
    steps: list[dict] = []

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        # stream-json shapes vary by CLI version; try common keys
        msg = obj.get("message") or obj
        if isinstance(msg, dict):
            content = msg.get("content") or msg.get("delta", {})
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use":
                        continue
                    name = block.get("name", "")
                    inp = block.get("input") or {}
                    if name == "Bash" and isinstance(inp, dict):
                        cmd = inp.get("command") or ""
                        if _looks_like_llm_wiki_bash(cmd):
                            argv = _split_llm_wiki_argv(cmd)
                            if argv:
                                step: dict = {"argv": argv, "expect_exit_0": True, "stdout_contains": []}
                                steps.append(step)
                            else:
                                steps.append(
                                    {
                                        "command": cmd,
                                        "expect_exit_0": True,
                                        "stdout_contains": [],
                                    }
                                )
        # Anthropic-style message with tool_use blocks
        if obj.get("type") == "content_block_delta":
            pass

    # De-duplicate consecutive identical argv steps
    deduped: list[dict] = []
    for s in steps:
        if deduped and deduped[-1].get("argv") == s.get("argv") and deduped[-1].get("command") == s.get(
            "command"
        ):
            continue
        deduped.append(s)

    return {
        "name": path.stem.split("-")[0] if path.stem else "golden",
        "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "steps": deduped or [{"argv": ["validate"], "expect_exit_0": True, "stdout_contains": ["OK"]}],
        "file_checks": [
            {"path": "wiki/index.md", "exists": True},
            {"path": "config.json", "exists": True},
        ],
        "purge_vault_after": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract golden JSON from stream-json recording")
    ap.add_argument("recording", type=Path, help="Path to .jsonl recording")
    ap.add_argument("-o", "--output", type=Path, help="Write golden fixture (default: stdout)")
    args = ap.parse_args()
    if not args.recording.is_file():
        print(f"Not a file: {args.recording}", file=sys.stderr)
        return 1
    data = extract_from_recording(args.recording)
    text = json.dumps(data, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
