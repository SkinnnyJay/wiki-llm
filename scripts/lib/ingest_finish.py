"""Shared post-ingest pipeline: merged frontmatter write, dedup, tagging, security, git."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from ingest import security as secscan
from ingest.dedup import check_duplicate, content_hash, register_hash, strip_llm_wiki_keys
from ingest.tagger import detect_tags, merge_tags, register_tags
from lib import git as vgit
from lib.hooks import maybe_play_sound


def _build_llm_wiki_frontmatter(
    security: dict[str, Any] | None,
    tags: list[str],
    tags_source: str,
    hash_str: str,
) -> str:
    """Render merged llm_wiki_* YAML block. If security is None, omit llm_wiki_security (sidecar mode)."""
    lines: list[str] = []
    if security is not None:
        lines.extend(
            [
                "llm_wiki_security:",
                f"  prompt_injection: {security['prompt_injection']!r}",
                f"  signals: {json.dumps(security['signals'])}",
            ]
        )
    lines.extend(
        [
            f"llm_wiki_tags: {json.dumps(tags)}",
            f"llm_wiki_tags_source: {tags_source!r}",
            f"llm_wiki_content_hash: {hash_str}",
        ]
    )
    return "---\n" + "\n".join(lines) + "\n---\n\n"


def _inject_merged_frontmatter(clean_body: str, fm_block: str) -> str:
    """Prepend merged llm_wiki frontmatter, preserving any existing author frontmatter."""
    if clean_body.startswith("---\n"):
        # Existing author frontmatter — insert llm_wiki block after it
        end = clean_body.find("\n---", 3)
        if end != -1:
            return clean_body[: end + 4] + "\n" + fm_block + clean_body[end + 4 :].lstrip("\n")
    return fm_block + clean_body


def post_ingest(
    vault: Path,
    cfg: dict[str, Any],
    output_path: Path,
    *,
    force: bool = False,
    force_security: bool = False,
    suppress_sound: bool = False,
    commit_body: str | None = None,
    manual_tags: list[str] | None = None,
) -> int:
    """
    Single-pass merged frontmatter pipeline. Returns shell exit code (0, 1, or 2).

    Pipeline:
      1. Read file → clean_body (strip existing llm_wiki_* keys)
      2. Hash clean_body
      3. Dedup check
      4. Security scan
      5. Tag detection
      6. Build + write merged frontmatter (one write)
      7. register_hash, register_tags
      8. Git snapshot
    """
    # Step 1 — read and strip
    raw_text = output_path.read_text(encoding="utf-8", errors="replace")
    clean_body = strip_llm_wiki_keys(raw_text)

    # Step 2 — hash
    sec_cfg = cfg.get("ingestion_security") or {}
    dedup_cfg = cfg.get("ingestion_dedup") or {}
    tag_cfg = cfg.get("ingestion_tagging") or {}
    hash_str = ""
    if dedup_cfg.get("enabled", True):
        hash_str = content_hash(clean_body)

    # Step 3 — dedup
    if hash_str:
        dupes = check_duplicate(vault, hash_str)
        dupes = [p for p in dupes if p != output_path]
        if dupes:
            print(f"DEDUP: duplicate content detected — matches {dupes[0]}")
            if dedup_cfg.get("block_on_duplicate") and not force:
                output_path.unlink(missing_ok=True)
                print(
                    "Blocked (ingestion_dedup.block_on_duplicate). Use --force to override.",
                    file=sys.stderr,
                )
                return 2

    # Step 4 — security scan (pure text, no file I/O)
    security_result: dict[str, Any] | None = {"prompt_injection": "low_risk", "signals": []}
    write_security_to_frontmatter = sec_cfg.get("log_to_raw_frontmatter", True)
    if force_security or sec_cfg.get("enabled", False):
        scan = secscan.scan_text(clean_body)
        security_result = scan.to_dict()
        if scan.prompt_injection == "suspected":
            print("SECURITY: prompt_injection suspected — signals:", ", ".join(scan.signals))
            if sec_cfg.get("llm_triage"):
                print(
                    "ingestion_security.llm_triage is on — review before merging.",
                    file=sys.stderr,
                )
            if sec_cfg.get("block_on_suspected") and not force:
                print(
                    "Blocked (ingestion_security.block_on_suspected). Use --force to override.",
                    file=sys.stderr,
                )
                return 2
        # Sidecar mode: write .security.json instead of frontmatter
        if not write_security_to_frontmatter:
            secscan.write_sidecar(output_path, scan)
            security_result = None  # omit llm_wiki_security from merged FM

    # Step 5 — tag detection
    tags: list[str] = []
    tags_source = "auto"
    if tag_cfg.get("enabled", True):
        try:
            tag_path = output_path.relative_to(vault)
        except ValueError:
            tag_path = output_path
        auto_result = detect_tags(clean_body, tag_path, cfg) if tag_cfg.get("auto_detect", True) else None
        auto_tags = auto_result.tags if auto_result else []
        merged = merge_tags(
            auto=auto_tags,
            manual=manual_tags or [],
            llm=[],  # LLM-suggested tags are not wired through post_ingest (only auto + manual)
        )
        tags = merged.tags
        tags_source = merged.source

    # Step 6 — build merged frontmatter and write file (ONCE)
    fm_block = _build_llm_wiki_frontmatter(security_result, tags, tags_source, hash_str)
    new_text = _inject_merged_frontmatter(clean_body, fm_block)
    output_path.write_text(new_text, encoding="utf-8")

    # Step 7 — update indexes
    if hash_str:
        register_hash(vault, hash_str, output_path)
    if tags:
        register_tags(vault, tags, output_path)

    # Step 8 — git snapshot
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

    # Optional knowledge graph refresh after raw ingest
    kg_cfg = cfg.get("knowledge_graph") or {}
    if kg_cfg.get("enabled", True) and kg_cfg.get("auto_update_on_ingest", True):
        try:
            from lib.knowledge_graph import get_kg_backend

            kg = get_kg_backend(vault, cfg)
            summary = kg.rebuild(vault)
            print(f"KG: auto-update — added {summary.get('added', 0)} triple(s)")
        except Exception as e:
            print(f"KG: auto-update skipped: {e}", file=sys.stderr)

    return 0
