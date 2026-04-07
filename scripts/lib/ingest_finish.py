"""Shared security scan + optional git snapshot after ingest."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from lib import git as vgit
from lib.hooks import maybe_play_sound
from ingest import security as secscan


def post_ingest(
    vault: Path,
    cfg: dict[str, Any],
    output_path: Path,
    *,
    force: bool = False,
    force_security: bool = False,
    suppress_sound: bool = False,
    commit_body: str | None = None,
) -> int:
    """Run ingestion_security scan and optional git snapshot. Returns shell exit code (0 or 2)."""
    scan = secscan.scan_file(output_path, cfg, force=force_security)
    if scan and scan.prompt_injection == "suspected":
        print("SECURITY: prompt_injection suspected — signals:", ", ".join(scan.signals))
        if cfg.get("ingestion_security", {}).get("llm_triage"):
            print(
                "ingestion_security.llm_triage is on — use the wiki-ingest skill / Claude to review "
                "before merging this raw file into wiki/.",
                file=sys.stderr,
            )
        if cfg.get("ingestion_security", {}).get("block_on_suspected") and not force:
            print("Blocked (ingestion_security.block_on_suspected). Use --force to override.", file=sys.stderr)
            return 2
    if cfg.get("git", {}).get("snapshot_after_ingest"):
        try:
            prefix = cfg.get("git", {}).get("snapshot_message_prefix") or "[ingest]"
            subject = f"{prefix} {output_path.name}"
            msg = f"{subject}\n\n{commit_body}" if commit_body else subject
            print(vgit.git_snapshot(vault, cfg, msg))
        except vgit.GitDisabledError:
            pass
        except Exception as e:
            print("git snapshot:", e, file=sys.stderr)
    if not suppress_sound:
        maybe_play_sound(cfg, "ingest")
    return 0
