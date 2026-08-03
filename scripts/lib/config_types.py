"""Narrow types for stable sections of the user-editable vault config."""

from __future__ import annotations

from typing import Any, Literal, TypedDict, cast

StorageKey = Literal[
    "search_db",
    "kg_db",
    "kg_sqlite_db",
    "chromadb_dir",
    "metrics_db",
]


class StoragePaths(TypedDict, total=False):
    search_db: str
    kg_db: str
    kg_sqlite_db: str
    chromadb_dir: str
    metrics_db: str


class McpConfig(TypedDict, total=False):
    enabled: bool
    transport: Literal["stdio", "sse"]
    port: int
    host: str
    search_backend: Literal["fts5", "grep", "chromadb", "hybrid"]
    hybrid_rrf_k: int
    tools_mode: Literal["full", "read_only", "custom"]
    tools_allowlist: list[str]
    max_response_chars: int
    read_page_max_chars: int
    configure_allowlist: list[str]
    benchmark_tool_enabled: bool
    ingest_enabled: bool
    compile_enabled: bool
    compile_allow_site: bool
    allow_local_file_ingest: bool
    allow_force_security: bool
    sse_require_loopback: bool
    sse_token: str
    sse_allow_empty_token: bool
    status_file_count_ttl_seconds: int


def storage_paths(config: dict[str, Any]) -> StoragePaths:
    """Return the storage subsection after validating its runtime shape."""
    raw = config.get("storage")
    return cast(StoragePaths, raw) if isinstance(raw, dict) else {}


def mcp_config(config: dict[str, Any]) -> McpConfig:
    """Return the MCP subsection after validating its runtime shape."""
    raw = config.get("mcp")
    return cast(McpConfig, raw) if isinstance(raw, dict) else {}
