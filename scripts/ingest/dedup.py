"""Content hash and duplicate detection for raw/ ingest."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

# Matches a YAML frontmatter block that contains ONLY llm_wiki_* keys
_SOLO_LLM_BLOCK = re.compile(
    r"^---\n(?:llm_wiki_\S+:.*\n)+---\n?", re.MULTILINE
)


def strip_llm_wiki_keys(body: str) -> str:
    """
    Remove llm_wiki_* frontmatter keys (and their nested YAML values) from body.

    Handles two layouts:
    - Combined block: author keys + llm_wiki_* keys in one ---/--- pair.
      Strip only llm_wiki_* key lines and any immediately following indented lines.
    - Separate second ---/--- block containing only llm_wiki_* keys: remove entire block.

    Example combined block:
        ---
        title: Auth
        llm_wiki_security:
          prompt_injection: 'low_risk'
          signals: []
        llm_wiki_tags: [auth]
        ---
    → strips llm_wiki_security (+ its two indented children) and llm_wiki_tags.
    """
    # Case 1: separate solo llm_wiki block (second --- block, only llm_wiki_* keys)
    body = _SOLO_LLM_BLOCK.sub("", body)

    # Case 2: combined block — strip llm_wiki_* lines + indented continuation lines
    if body.startswith("---\n"):
        end = body.find("\n---", 3)
        if end != -1:
            fm_content = body[4:end]
            # Remove any llm_wiki_* key and its indented continuation lines
            # Pattern: line starting with llm_wiki_, followed by zero or more
            # lines that start with whitespace (nested YAML values)
            cleaned = re.sub(
                r"^llm_wiki_\w+:.*(?:\n[ \t]+.*)*\n?",
                "",
                fm_content,
                flags=re.MULTILINE,
            )
            if cleaned.strip():
                body = "---\n" + cleaned.rstrip("\n") + "\n" + body[end:]
            else:
                # All lines were llm_wiki_* — remove entire fm block
                body = body[end + 4 :].lstrip("\n")
    return body


def content_hash(body: str) -> str:
    """SHA-256 of body after stripping llm_wiki_* keys. Format: 'sha256:<hex>'."""
    clean = strip_llm_wiki_keys(body)
    digest = hashlib.sha256(clean.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _index_path(vault: Path) -> Path:
    return vault / "raw" / ".hashes.json"


def _load_index(vault: Path) -> dict[str, list[str]]:
    from lib.json_index import load_json_object

    p = _index_path(vault)
    return load_json_object(p, default_if_missing={})  # type: ignore[return-value]


def _save_index(vault: Path, index: dict[str, Any]) -> None:
    from lib.json_index import atomic_write_json

    atomic_write_json(_index_path(vault), index)


def check_duplicate(vault: Path, hash_str: str) -> list[Path]:
    """Return all paths with matching hash. Empty list = no duplicate."""
    index = _load_index(vault)
    paths = index.get(hash_str, [])
    return [Path(p) for p in paths]


def register_hash(vault: Path, hash_str: str, path: Path) -> None:
    """Add path under hash_str in .hashes.json. Atomic write."""
    index = _load_index(vault)
    existing = index.get(hash_str, [])
    str_path = str(path)
    if str_path not in existing:
        existing = existing + [str_path]
    index[hash_str] = existing
    _save_index(vault, index)


def rebuild_index(vault: Path) -> int:
    """Rebuild .hashes.json from llm_wiki_content_hash frontmatter. Returns count."""
    raw_dir = vault / "raw"
    if not raw_dir.exists():
        return 0
    index: dict[str, list[str]] = {}
    count = 0
    for md in sorted(raw_dir.rglob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^llm_wiki_content_hash:\s*(\S+)", text, re.MULTILINE)
        if m:
            h = m.group(1)
            index.setdefault(h, [])
            sp = str(md)
            if sp not in index[h]:
                index[h].append(sp)
            count += 1
    _save_index(vault, index)
    return count
