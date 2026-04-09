#!/usr/bin/env python3
"""Regenerate agent-facing docs from docs/AGENTS.shared.md.

From repo root, run:

  bin/llm-wiki sync-agent-docs

or:

  python3 scripts/sync_agent_docs.py

Updates:
  - rules/llm-wiki.mdc (Cursor rule body after YAML frontmatter)
  - .claude/rules/llm-wiki.md (Claude Code project rules; same body as the .mdc, no YAML)
  - AGENTS.md and CLAUDE.md (between <!-- BEGIN AGENTS_SHARED --> / <!-- END AGENTS_SHARED -->)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MARKER_START = "<!-- BEGIN AGENTS_SHARED -->"
MARKER_END = "<!-- END AGENTS_SHARED -->"

FRONTMATTER_YAML = """---
description: wiki-llm plugin — CLI, commands/, skills, and vault workflows for Cursor
alwaysApply: true
---

"""

RULE_INTRO = "# wiki-llm (this repo)\n\n"


def _shared_body(repo: Path) -> tuple[Path, str] | None:
    """Return (path to shared file, normalized body) or None if missing."""
    shared = repo / "docs" / "AGENTS.shared.md"
    if not shared.is_file():
        return None
    body = shared.read_text(encoding="utf-8").strip() + "\n"
    return shared, body


def expected_rule_mdc(body: str) -> str:
    return FRONTMATTER_YAML + RULE_INTRO + body


def expected_claude_rule_md(body: str) -> str:
    return RULE_INTRO + body


def _replace_marked_block(path: Path, body: str) -> None:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    replacement = MARKER_START + "\n" + body.rstrip() + "\n" + MARKER_END
    if not pattern.search(text):
        print(f"error: markers not found in {path}", file=sys.stderr)
        raise SystemExit(1)
    new_text = pattern.sub(replacement, text, count=1)
    path.write_text(new_text, encoding="utf-8")


def verify_agent_docs(repo: Path, *, quiet: bool = False) -> int:
    """
    Return 0 if ``rules/llm-wiki.mdc``, ``.claude/rules/llm-wiki.md``, and marked
    sections in ``AGENTS.md`` / ``CLAUDE.md`` match ``docs/AGENTS.shared.md``.
    On success, prints a one-line OK unless ``quiet`` is True.
    """
    got = _shared_body(repo)
    if got is None:
        shared = repo / "docs" / "AGENTS.shared.md"
        print(f"error: missing {shared} (not the llm-wiki plugin repo?)", file=sys.stderr)
        return 1
    _shared_path, body = got
    errs = 0
    rule = repo / "rules" / "llm-wiki.mdc"
    claude_rule = repo / ".claude" / "rules" / "llm-wiki.md"
    want_rule = expected_rule_mdc(body)
    want_claude = expected_claude_rule_md(body)
    if not rule.is_file() or rule.read_text(encoding="utf-8") != want_rule:
        print(f"error: {rule} out of sync with {_shared_path}", file=sys.stderr)
        errs += 1
    if not claude_rule.is_file() or claude_rule.read_text(encoding="utf-8") != want_claude:
        print(f"error: {claude_rule} out of sync with {_shared_path}", file=sys.stderr)
        errs += 1
    marker_pat = re.compile(
        re.escape(MARKER_START) + r"(.*?)" + re.escape(MARKER_END),
        re.DOTALL,
    )
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = repo / name
        if not path.is_file():
            print(f"error: missing {path}", file=sys.stderr)
            errs += 1
            continue
        text = path.read_text(encoding="utf-8")
        m = marker_pat.search(text)
        if not m:
            print(f"error: {MARKER_START} … {MARKER_END} not found in {path}", file=sys.stderr)
            errs += 1
            continue
        inner = m.group(1).strip() + "\n"
        if inner != body:
            print(f"error: marked block in {path} out of sync with {_shared_path}", file=sys.stderr)
            errs += 1
    if errs:
        print("hint: run: bin/llm-wiki sync-agent-docs", file=sys.stderr)
        return 1
    if not quiet:
        print(f"agent docs: OK (match {_shared_path})")
    return 0


def sync_agent_docs(repo: Path) -> int:
    """Sync generated agent docs under ``repo`` (plugin root). Returns exit status."""
    got = _shared_body(repo)
    if got is None:
        shared = repo / "docs" / "AGENTS.shared.md"
        print(f"error: missing {shared} (not the llm-wiki plugin repo?)", file=sys.stderr)
        return 1
    shared, body = got
    rule = repo / "rules" / "llm-wiki.mdc"
    claude_rule = repo / ".claude" / "rules" / "llm-wiki.md"
    rule_body = FRONTMATTER_YAML + RULE_INTRO + body
    rule.write_text(rule_body, encoding="utf-8")
    claude_rule.write_text(RULE_INTRO + body, encoding="utf-8")
    for name in ("AGENTS.md", "CLAUDE.md"):
        _replace_marked_block(repo / name, body)
    print(
        f"Synced from {shared} -> {rule}, {claude_rule}, AGENTS.md, CLAUDE.md",
    )
    return 0


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    raise SystemExit(sync_agent_docs(repo))


if __name__ == "__main__":
    main()
