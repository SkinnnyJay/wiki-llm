"""Load and merge llm-wiki/config.json with defaults."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from lib.config_types import StorageKey, storage_paths

DEFAULTS: dict[str, Any] = {
    "version": 1,
    "wiki_root": "llm-wiki",
    "persona": {
        "name": "Gennie",
    },
    "viewer": {
        "enabled": True,
        "port": 8765,
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
    "ingestion": {
        # Maximum response body accepted by the built-in URL ingest adapter.
        "max_download_bytes": 32 * 1024 * 1024,
    },
    "layers": {
        "wake_max_tokens": 200,
        "l1_topic_bullets": 8,
    },
    "graph": {
        "port": 8890,
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
        "hybrid_rrf_k": 60,
        # Tool surface: full (default) | read_only | custom (use tools_allowlist; empty allowlist = read_only)
        "tools_mode": "full",
        "tools_allowlist": [],
        # 0 = unlimited JSON response size
        "max_response_chars": 500000,
        # 0 = no truncation of wiki_read_page body (still subject to max_response_chars on output)
        "read_page_max_chars": 0,
        # Empty allowlist: deny mcp.*/security.*/ingestion_security.* and path-bearing keys
        "configure_allowlist": [],
        "benchmark_tool_enabled": True,
        "ingest_enabled": True,
        # Allow wiki_ingest adapter=file / local PDF paths (default off — host path read)
        "allow_local_file_ingest": False,
        # Allow wiki_ingest force_security=true (default off)
        "allow_force_security": False,
        # HTTP MCP: refuse non-loopback bind when true; set false only with firewall/TLS/proxy
        "sse_require_loopback": True,
        # If non-empty, HTTP MCP requires Authorization: Bearer <token> or X-LLM-Wiki-Token
        "sse_token": "",
        # Allow empty sse_token on non-loopback (insecure; default false)
        "sse_allow_empty_token": False,
        # Cache TTL for raw/wiki *.md counts in wiki_status (seconds)
        "status_file_count_ttl_seconds": 45,
    },
    "knowledge_graph": {
        "enabled": True,
        "backend": "json",
        "auto_update_on_ingest": True,
        "entity_detection": True,
        "fact_check_on_add": True,
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
        "append_repo_runs_jsonl": False,
        "repo_runs_jsonl_path": "docs/memory/benchmarks/metrics/runs.jsonl",
        "write_run_sidecar": True,
        "debug_rerank": False,
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
            "or_late_rrf_weight": 0.15,
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
                "invoke": "auto",
                "model": "claude-sonnet-4-6",
                "api_key_env": "ANTHROPIC_API_KEY",
                "max_candidates": 80,
                "max_chars": 3600,
                "max_picks": 5,
                "excerpt_mode": "head_tail",
                "cli_argv": None,
                "cli_timeout_s": 180,
                "fuse_original_rrf": True,
                "fuse_original_weight": 0.35,
                "fuse_rrf_k": 60,
                "invoke_when": "always",
                "adaptive_head": 5,
                "adaptive_lookback": 24,
                "adaptive_tail_margin": 0.12,
                "adaptive_min_head_lex": 3.5,
                "adaptive_max_chars": 12000,
                "adaptive_confidence_threshold": 0.5,
                "parallel_workers": 1,
                "persistent_cli_pool": False,
                "persistent_pool_size": 4,
                "session_dedup": False,
                "cross_encoder_model": "mixedbread-ai/mxbai-rerank-large-v1",
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
        "peers": {
            "cache_dir": "~/.cache/llm-wiki-benchmarks/peers",
            "strict": False,
        },
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


def merge_missing_defaults(config: dict[str, Any]) -> list[str]:
    """Add missing DEFAULTS keys in place without changing configured values.

    Returns leaf dotted paths for newly inserted values (nested dict defaults
    expand to their leaf keys).
    """
    added: list[str] = []

    def _leaf_paths(default: Any, prefix: str) -> list[str]:
        if isinstance(default, dict):
            out: list[str] = []
            for key, value in default.items():
                out.extend(_leaf_paths(value, f"{prefix}.{key}"))
            return out or [prefix]
        return [prefix]

    def visit(current: dict[str, Any], defaults: dict[str, Any], prefix: str = "") -> None:
        for key, default in defaults.items():
            path = f"{prefix}.{key}" if prefix else key
            if key not in current:
                current[key] = deepcopy(default)
                added.extend(_leaf_paths(default, path))
            elif isinstance(default, dict) and isinstance(current[key], dict):
                visit(current[key], default, path)

    visit(config, DEFAULTS)
    return added


def load_config(vault: Path) -> dict[str, Any]:
    path = vault / "config.json"
    if not path.is_file():
        return deepcopy(DEFAULTS)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return deepcopy(DEFAULTS)
    return deep_merge(DEFAULTS, data)


def resolve_storage_path(vault: Path, cfg: dict[str, Any], key: StorageKey) -> Path:
    """Resolve a storage path from config. Relative paths anchor to vault root.

    Paths must stay under the vault (absolute outside-vault paths raise ValueError).
    """
    from lib.path_safety import resolve_under_vault

    storage = storage_paths(cfg)
    defaults = dict(DEFAULTS.get("storage") or {})
    raw = storage.get(key, defaults.get(key))
    if raw is None:
        raw = defaults.get(key)
    rel = str(raw or "").strip() or str(defaults.get(key) or key)
    resolved = resolve_under_vault(vault, rel)
    if resolved is None:
        raise ValueError(
            f"storage.{key} escapes vault ({rel!r}); use a vault-relative path"
        )
    return resolved


def storage_warnings(vault: Path, cfg: dict[str, Any]) -> list[str]:
    """Return warnings for storage paths that cannot be resolved under the vault."""
    out: list[str] = []
    for key in ("search_db", "kg_db", "kg_sqlite_db", "chromadb_dir", "metrics_db"):
        try:
            resolve_storage_path(vault, cfg, key)  # type: ignore[arg-type]
        except ValueError as e:
            out.append(str(e))
    return out


def save_config(vault: Path, cfg: dict[str, Any]) -> None:
    vault.mkdir(parents=True, exist_ok=True)
    path = vault / "config.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
