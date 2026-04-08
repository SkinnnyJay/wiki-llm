"""Vault-scoped git helpers. All operations use cwd=vault; gated by config."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

# Default phase order for classification (first matching prefix wins)
_LIFECYCLE_ORDER = ("ingest", "prepare", "wiki", "build", "graph", "research", "config")


class GitDisabledError(RuntimeError):
    pass


def _require_git(cfg: dict[str, Any]) -> None:
    if not cfg.get("git", {}).get("enabled"):
        raise GitDisabledError("Vault git is disabled in llm-wiki/config.json (git.enabled: false).")


def _run(vault: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(vault), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def git_init(vault: Path, cfg: dict[str, Any]) -> str:
    _require_git(cfg)
    if (vault / ".git").exists():
        return "Git already initialized in vault."
    _run(vault, ["init"], check=True)
    return "Initialized git repository in vault."


def git_status(vault: Path, cfg: dict[str, Any]) -> str:
    _require_git(cfg)
    if not (vault / ".git").exists():
        return "No .git in vault. Run: llm-wiki git init"
    p = _run(vault, ["status", "--short"], check=True)
    return p.stdout or "(clean)"


def git_log(vault: Path, cfg: dict[str, Any], n: int = 20, since: str | None = None, grep: str | None = None) -> str:
    _require_git(cfg)
    if not (vault / ".git").exists():
        return "No .git in vault."
    args = ["log", f"-n{n}", "--oneline", "--decorate"]
    if since:
        args.extend(["--since", since])
    if grep:
        args.extend(["--grep", grep])
    p = _run(vault, args, check=True)
    return p.stdout


def lifecycle_prefixes(cfg: dict[str, Any]) -> list[tuple[str, str]]:
    """Return (phase_id, prefix_substring) for classifying commit subjects. Ingest uses snapshot_message_prefix if phase missing."""
    g = cfg.get("git") or {}
    raw = ((g.get("lifecycle") or {}).get("phases")) or {}
    out: list[tuple[str, str]] = []
    if isinstance(raw, dict):
        for pid in _LIFECYCLE_ORDER:
            p = raw.get(pid)
            if p:
                out.append((pid, str(p)))
        for pid, p in raw.items():
            if pid not in _LIFECYCLE_ORDER and p:
                out.append((pid, str(p)))
    if not out:
        out = [
            ("ingest", g.get("snapshot_message_prefix") or "[ingest]"),
            ("wiki", "[wiki]"),
            ("build", "[build]"),
            ("graph", "[graph]"),
            ("research", "[research]"),
            ("config", "[config]"),
        ]
    else:
        # Ensure ingest aligns with legacy snapshot_message_prefix when phases.ingest absent
        has_ingest = any(x[0] == "ingest" for x in out)
        if not has_ingest:
            out.insert(0, ("ingest", g.get("snapshot_message_prefix") or "[ingest]"))
    return out


def classify_lifecycle_subject(subject: str, cfg: dict[str, Any]) -> str:
    """Return phase id or 'unlabeled' if no prefix matched."""
    s = subject.strip()
    for pid, prefix in lifecycle_prefixes(cfg):
        if prefix and s.startswith(prefix):
            return pid
    return "unlabeled"


def git_lifecycle_audit(
    vault: Path,
    cfg: dict[str, Any],
    *,
    n: int = 40,
    phase: str | None = None,
    since: str | None = None,
) -> list[dict[str, str]]:
    """Recent commits with lifecycle phase for auditing flow progression."""
    fetch_n = min(500, n * 15) if phase else n
    rows = git_log_json(vault, cfg, n=fetch_n, since=since)
    enriched: list[dict[str, str]] = []
    for r in rows:
        subj = r.get("subject", "")
        pid = classify_lifecycle_subject(subj, cfg)
        if phase and pid != phase:
            continue
        enriched.append({**r, "phase": pid})
        if len(enriched) >= n:
            break
    return enriched


def prefix_for_phase(cfg: dict[str, Any], phase: str) -> str | None:
    """Message prefix for a named phase (for snapshot --phase)."""
    g = cfg.get("git") or {}
    phases = ((g.get("lifecycle") or {}).get("phases")) or {}
    if isinstance(phases, dict) and phase in phases and phases[phase]:
        return str(phases[phase])
    if phase == "ingest":
        return g.get("snapshot_message_prefix") or "[ingest]"
    return None


def git_log_json(
    vault: Path,
    cfg: dict[str, Any],
    n: int = 20,
    *,
    since: str | None = None,
) -> list[dict[str, str]]:
    _require_git(cfg)
    if not (vault / ".git").exists():
        return []
    fmt = "%H%x1f%s%x1f%an%x1f%ad"
    args = ["log", f"-n{n}", f"--pretty=format:{fmt}", "--date=short"]
    if since:
        args.extend(["--since", since])
    p = _run(
        vault,
        args,
        check=True,
    )
    rows: list[dict[str, str]] = []
    for line in p.stdout.strip().splitlines():
        parts = line.split("\x1f")
        if len(parts) >= 4:
            rows.append(
                {"hash": parts[0], "subject": parts[1], "author": parts[2], "date": parts[3]}
            )
    return rows


def git_diff(vault: Path, cfg: dict[str, Any], staged: bool = False) -> str:
    _require_git(cfg)
    if not (vault / ".git").exists():
        return "No .git in vault."
    args = ["diff"]
    if staged:
        args.append("--cached")
    p = _run(vault, args, check=False)
    return p.stdout or "(no diff)"


def git_snapshot(vault: Path, cfg: dict[str, Any], message: str) -> str:
    _require_git(cfg)
    if not (vault / ".git").exists():
        return "No .git in vault. Run: llm-wiki git init"
    globs = cfg.get("git", {}).get("tracked_globs") or ["wiki/", "raw/", "CLAUDE.md", "config.json"]
    for g in globs:
        path = vault / g.rstrip("/")
        if path.is_file() or path.is_dir():
            _run(vault, ["add", "--", g], check=False)
    p = _run(vault, ["commit", "-m", message], check=False)
    if p.returncode != 0:
        return p.stderr.strip() or p.stdout.strip() or "(nothing to commit)"
    return f"Committed: {message}"


def print_git_log_json(vault: Path, cfg: dict[str, Any], n: int = 20) -> None:
    print(json.dumps(git_log_json(vault, cfg, n=n), indent=2))
