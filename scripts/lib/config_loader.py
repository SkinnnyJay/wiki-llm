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
    "benchmark": {
        "enabled": True,
        "compress_method": "raw",
        "data_cache_dir": "~/.cache/llm-wiki-benchmarks",
        "results_dir": ".benchmarks",
        "auto_record_metrics": True,
        "search": {
            "backend": "fts5",
            "hybrid_enabled": False,
            "hybrid_fusion": "rrf",
            "hybrid_k": 60,
            "query_expansion": False,
            "triple_fts_rrf": False,
            "prf_rrf": True,
            "tfidf_rrf": True,
            "tfidf_head_tail": True,
            "tfidf_max_chars": 80000,
            "tfidf_rrf_weight": 1.0,
            "or_late_rrf_weight": 0,
            "rrf_boost_or": 2,
            "and_rrf": True,
            "final_borda": False,
            "refine_head_lexical": False,
            "refine_head_n": 40,
            "dual_fts_rrf": False,
            "lexical_rrf": False,
            "rerank_enabled": False,
            "rerank_top_n": 80,
            "rerank_llm": {
                "enabled": False,
                "benchmark_auto": False,
                "provider": "anthropic",
                "invoke": "anthropic_api",
                "model": "claude-3-5-haiku-20241022",
                "api_key_env": "ANTHROPIC_API_KEY",
                "max_candidates": 80,
                "max_chars": 3600,
                "excerpt_mode": "head_tail",
                "cli_argv": None,
                "cli_timeout_s": 180,
            },
        },
        "chunking": {
            "strategy": "document",
            "chunk_size": 512,
            "chunk_overlap": 128,
        },
        "steno": {
            "vowel_drop_min_length": 5,
            "preserve_quoted": True,
            "custom_abbreviations": {},
        },
        "prune": {"removal_percentile": 30},
        "extract": {"max_entities": 5, "max_topics": 3},
        "compact": {"keep_percentile": 60, "min_sentence_score": 0.3},
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
