"""Shared MCP runtime state and vault helpers.

Tool modules import from here. Tests that historically patched ``mcp_server._vault``
should patch attributes on this module (or use ``mcp_server`` re-exports which
alias the same names via ``mcp_server`` module-level assignment after initialize).
"""
from __future__ import annotations

import copy
import os
import threading
import time
from pathlib import Path
from typing import Any

from lib.config_loader import load_config
from lib.config_types import McpConfig, mcp_config
from lib.knowledge_graph import get_kg_backend
from lib.metrics import MetricsRecorder, get_metrics as factory_metrics
from lib.paths import resolve_vault
from lib.search import get_search_backend

_vault: Path | None = None
_cfg: dict[str, Any] = {}
_metrics: Any = None
_search: Any = None
_kg: Any = None
_state_lock = threading.RLock()

_CONFIGURE_DENY_PREFIXES = (
    "mcp.",
    "security.",
    "ingestion_security.",
    "storage.",
)
_CONFIGURE_DENY_EXACT = frozenset(
    {
        "mcp",
        "security",
        "ingestion_security",
        "storage",
        "memory.dir",
        "benchmark.data_cache_dir",
        "benchmark.results_dir",
    }
)

CONFIGURE_RESTART_KEYS = frozenset(
    {
        "mcp.enabled",
        "mcp.transport",
        "mcp.port",
        "mcp.host",
        "mcp.sse_token",
        "mcp.sse_require_loopback",
    }
)

_vault_md_count_cache: dict[str, Any] = {
    "t": 0.0,
    "raw_sig": None,
    "wiki_sig": None,
    "raw_n": 0,
    "wiki_n": 0,
}


def require_vault() -> Path:
    """Return the active vault path (call after ``vault_ok()`` or initialize)."""
    if _vault is None:
        raise RuntimeError("MCP vault not initialized")
    return _vault


def vault_ok() -> bool:
    return _vault is not None and (_vault / "config.json").is_file()


def no_vault() -> dict[str, Any]:
    return {"error": "No vault found", "hint": "Run: llm-wiki setup"}


def get_cfg() -> dict[str, Any]:
    return _cfg


def set_cfg(cfg: dict[str, Any]) -> None:
    global _cfg
    _cfg = cfg


def get_search() -> Any:
    return _search


def set_search(search: Any) -> None:
    global _search
    _search = search


def get_kg() -> Any:
    return _kg


def set_kg(kg: Any) -> None:
    global _kg
    _kg = kg


def get_metrics() -> Any:
    return _metrics


def set_metrics(metrics: Any) -> None:
    global _metrics
    _metrics = metrics
    if _search is not None:
        _search._metrics = metrics  # type: ignore[attr-defined]
    if _kg is not None:
        _kg._metrics = metrics  # type: ignore[attr-defined]


def state_lock() -> threading.RLock:
    return _state_lock


def mcp_cfg() -> McpConfig:
    return mcp_config(_cfg)


def configure_key_allowed(key: str, rules: list[Any]) -> bool:
    """Allowlist for wiki_configure (fail closed for trust/path knobs)."""
    key = (key or "").strip()
    is_sensitive = key in _CONFIGURE_DENY_EXACT or any(
        key.startswith(p) for p in _CONFIGURE_DENY_PREFIXES
    )
    if not rules:
        return not is_sensitive
    for r in rules:
        if not isinstance(r, str):
            continue
        r = r.strip()
        if not r:
            continue
        if r.endswith("."):
            if key.startswith(r) or key == r[:-1]:
                return True
        elif key == r:
            return True
    return False


def _dir_sig(d: Path) -> tuple[int, int]:
    if not d.is_dir():
        return (0, 0)
    st = d.stat()
    return (int(st.st_mtime_ns), int(st.st_size))


def cached_md_counts() -> tuple[int, int]:
    """Return (raw_md_count, wiki_md_count) using mtime+TTL cache."""
    vault = require_vault()
    ttl = float(mcp_cfg().get("status_file_count_ttl_seconds") or 45)
    raw_dir = vault / "raw"
    wiki_dir = vault / "wiki"
    rs, ws = _dir_sig(raw_dir), _dir_sig(wiki_dir)
    now = time.monotonic()
    c = _vault_md_count_cache
    if (
        c.get("raw_sig") == rs
        and c.get("wiki_sig") == ws
        and now - float(c.get("t", 0)) < ttl
    ):
        return (int(c["raw_n"]), int(c["wiki_n"]))
    raw_n = len(list(raw_dir.rglob("*.md"))) if raw_dir.exists() else 0
    wiki_n = len(list(wiki_dir.rglob("*.md"))) if wiki_dir.exists() else 0
    c.update(
        {
            "t": now,
            "raw_sig": rs,
            "wiki_sig": ws,
            "raw_n": raw_n,
            "wiki_n": wiki_n,
        }
    )
    return raw_n, wiki_n


def metrics_recorder_for_read() -> Any:
    cfg = copy.deepcopy(_cfg)
    cfg.setdefault("metrics", {})["enabled"] = True
    return MetricsRecorder(require_vault(), cfg)


def safe_benchmark_data_path(data_arg: str | None) -> Path | None:
    """Resolve optional dataset path; must stay under vault or benchmark cache dir."""
    if not (data_arg or "").strip():
        return None
    p = Path(os.path.expanduser(str(data_arg).strip())).resolve()
    bcfg = _cfg.get("benchmark") or {}
    vault_r = require_vault().resolve()
    cache = Path(
        os.path.expanduser(bcfg.get("data_cache_dir", "~/.cache/llm-wiki-benchmarks"))
    ).resolve()
    for root in (vault_r, cache):
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue
    raise ValueError(
        f"data_path must be under vault ({vault_r}) or benchmark cache ({cache}); got {p}"
    )


def init_runtime(
    vault: Path | None = None,
    *,
    vault_override: str | Path | None = None,
) -> Path:
    """Load vault config and backends into module state. Returns vault path."""
    global _vault, _cfg, _metrics, _search, _kg
    override: str | None
    if vault is not None:
        override = str(vault)
    elif vault_override is not None:
        override = str(vault_override)
    else:
        override = None
    _vault = resolve_vault(override=override)
    os.environ["LLM_WIKI_VAULT"] = str(_vault.resolve())
    _cfg = load_config(_vault)
    _metrics = factory_metrics(_vault, _cfg)
    _search = get_search_backend(_vault, _cfg)
    _search._metrics = _metrics  # type: ignore[attr-defined]
    _kg = get_kg_backend(_vault, _cfg)
    _kg._metrics = _metrics  # type: ignore[attr-defined]
    return _vault
