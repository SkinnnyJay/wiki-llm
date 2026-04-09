"""Load and merge llm-wiki/config.json with defaults."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "version": 1,
    "wiki_root": "llm-wiki",
    "persona": {
        "name": "Gennie",
    },
    "viewer": {
        "enabled": True,
        "og_base_url": "",
        "open_file_scheme": "file",
    },
    "integrations": {},
    "git": {
        "enabled": False,
        "init_on_setup": False,
        "snapshot_after_ingest": False,
        "snapshot_after_build": False,
        "snapshot_message_prefix": "[ingest]",
        "include_diff_in_skill_context": False,
        "tracked_globs": ["wiki/", "raw/", "CLAUDE.md", "config.json"],
        "lifecycle": {
            "phases": {
                "ingest": "[ingest]",
                "prepare": "[prepare]",
                "wiki": "[wiki]",
                "build": "[build]",
                "graph": "[graph]",
                "research": "[research]",
                "config": "[config]",
            }
        },
    },
    "research_loop": {
        "enabled": False,
        "max_items_per_run": 8,
        "tasks_file": "research-tasks.json",
        "delay_seconds_between_fetches": 1.0,
    },
    "ingestion_security": {
        "enabled": True,
        "block_on_suspected": False,
        "log_to_raw_frontmatter": True,
        "llm_triage": False,
    },
    "ingestion_tagging": {
        "enabled": True,
        "auto_detect": True,
        "llm_detect": False,
    },
    "ingestion_dedup": {
        "enabled": True,
        "block_on_duplicate": False,
    },
    "graph": {
        "tag_edges": True,
        "include_raw_nodes": True,
        "curated_by_edges": True,
    },
    "hooks": {
        "sound": {
            "enabled": False,
            "command": ["afplay", "/System/Library/Sounds/Glass.aiff"],
            "on_ingest": True,
            "on_research_loop": True,
            "timeout_seconds": 30,
        }
    },
    "pdf": {
        # "pdf" = Claude Vision (best quality, ~$0.02/page, requires ANTHROPIC_API_KEY)
        # "pdf-marker" = Marker/Surya OCR (free, local, requires .venv-marker)
        "default_adapter": "pdf",
        # If estimated Vision cost exceeds this, auto-fallback to pdf-marker with a warning.
        # Set to null to always use Vision regardless of cost.
        "max_cost_usd": None,
    },
    "mcp": {
        "enabled": True,
        "transport": "stdio",
        "port": 8891,
        "host": "127.0.0.1",
        "search_backend": "fts5",
    },
    "knowledge_graph": {
        "enabled": True,
        "backend": "json",
        "auto_update_on_ingest": True,
    },
    "memory": {
        "enabled": False,
        "dir": "raw/memory",
        "max_sessions": 50,
    },
    "storage": {
        "search_db": ".search.sqlite3",
        "kg_db": ".kg.json",
        "kg_sqlite_db": ".kg.sqlite3",
        "chromadb_dir": ".chromadb",
        "metrics_db": ".metrics.jsonl",
    },
    "performance": {
        "sqlite": {
            "journal_mode": "wal",
            "synchronous": "normal",
            "cache_size": -8192,
            "mmap_size": 67108864,
            "busy_timeout": 5000,
        },
        "chromadb": {
            "collection_name": "wiki_pages",
            "distance_fn": "cosine",
            "batch_size": 100,
            "embedding_model": "default",
        },
    },
    "metrics": {
        "enabled": False,
        "max_file_size_mb": 50,
    },
}


def deep_merge(base: dict, extra: dict) -> dict:
    out = deepcopy(base)
    for k, v in extra.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out


def load_config(vault: Path) -> dict[str, Any]:
    path = vault / "config.json"
    if not path.is_file():
        return deepcopy(DEFAULTS)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return deepcopy(DEFAULTS)
    return deep_merge(DEFAULTS, data)


def resolve_storage_path(vault: Path, cfg: dict[str, Any], key: str) -> Path:
    """Resolve a storage path from config. Relative paths anchor to vault root."""
    storage = cfg.get("storage") or {}
    raw = storage.get(key, DEFAULTS["storage"][key])
    p = Path(raw)
    return p if p.is_absolute() else vault / p


def save_config(vault: Path, cfg: dict[str, Any]) -> None:
    vault.mkdir(parents=True, exist_ok=True)
    path = vault / "config.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
