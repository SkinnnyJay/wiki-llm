"""Shared assertions and failure logging for Claude/Codex skill eval tests."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
SKILL_EVAL_LOG = REPO / ".tmp" / "logs" / "skills_evals.md"


def _truncate(s: str, max_len: int = 12000) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 20] + "\n… [truncated] …\n"


def append_skill_eval_failure_log(
    backend: str,
    case: dict[str, Any],
    r: subprocess.CompletedProcess[str],
    exc: BaseException,
) -> None:
    """Append a failure block to ``.tmp/logs/skills_evals.md`` (gitignored)."""
    SKILL_EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    skill = case.get("skill", "?")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    out = (r.stdout or "") + (r.stderr or "")
    lines = [
        "---",
        f"## {skill} — {ts}",
        "",
        f"**Backend:** `{backend}`",
        "",
        f"**Error:** `{exc!r}`",
        "",
        f"**returncode:** {r.returncode}",
        "",
        "**prompt (excerpt):**",
        "",
        "```",
        _truncate(case.get("prompt", "")[:2000]),
        "```",
        "",
        "**combined stdout+stderr:**",
        "",
        "```",
        _truncate(out),
        "```",
        "",
    ]
    write_header = not SKILL_EVAL_LOG.is_file() or SKILL_EVAL_LOG.stat().st_size == 0
    with SKILL_EVAL_LOG.open("a", encoding="utf-8") as f:
        if write_header:
            f.write("# Skill eval failures (append-only)\n\n")
        f.write("\n".join(lines) + "\n")


def assert_skill_eval_case(
    case: dict[str, Any],
    r: subprocess.CompletedProcess[str],
    seeded_vault: Path,
) -> None:
    """Assert return code, keyword checks, and optional files."""
    assert r.returncode == 0, r.stderr + r.stdout
    out = (r.stdout or "") + (r.stderr or "")
    for kw in case.get("check_output", []):
        if not kw:
            continue
        assert kw.lower() in out.lower(), f"expected {kw!r} in output for {case['skill']}"
    anys = case.get("check_output_any")
    if anys:
        out_l = out.lower()
        alts = [a for a in anys if a]
        assert alts, f"check_output_any empty for {case['skill']}"
        assert any(a.lower() in out_l for a in alts), (
            f"expected one of {alts!r} in output for {case['skill']}"
        )
    for path, should_exist in case.get("check_files", []):
        assert (seeded_vault / path).exists() == should_exist
