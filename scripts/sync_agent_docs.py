#!/usr/bin/env python3
"""Regenerate agent-facing docs from docs/AGENTS.shared.md.

From repo root, run:

  bin/llm-wiki sync-agent-docs

or:

  python3 scripts/sync_agent_docs.py

Updates:
  - rules/llm-wiki.mdc (Cursor rule body after YAML frontmatter)
  - AGENTS.md and CLAUDE.md (between <!-- BEGIN AGENTS_SHARED --> / <!-- END AGENTS_SHARED -->)

  We do **not** write under ``plugin-root/.claude/`` — a ``.claude/`` directory in a Claude Code
  plugin breaks discovery of ``skills/`` at the plugin root (see anthropics/claude-code#44120).
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
    Return 0 if ``rules/llm-wiki.mdc`` and marked sections in ``AGENTS.md`` / ``CLAUDE.md``
    match ``docs/AGENTS.shared.md``.
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
    want_rule = expected_rule_mdc(body)
    if not rule.is_file() or rule.read_text(encoding="utf-8") != want_rule:
        print(f"error: {rule} out of sync with {_shared_path}", file=sys.stderr)
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
    rule_body = FRONTMATTER_YAML + RULE_INTRO + body
    rule.write_text(rule_body, encoding="utf-8")
    for name in ("AGENTS.md", "CLAUDE.md"):
        _replace_marked_block(repo / name, body)
    print(
        f"Synced from {shared} -> {rule}, AGENTS.md, CLAUDE.md",
    )
    return 0


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    raise SystemExit(sync_agent_docs(repo))


if __name__ == "__main__":
    main()
