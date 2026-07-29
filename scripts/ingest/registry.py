from __future__ import annotations

from pathlib import Path
from typing import Any

from ingest.adapters import ADAPTERS
from ingest.base import Adapter, IngestResult
from ingest.config import integration_config, integration_enabled

# Adapters whose primary input is a local filesystem path (MCP-gated).
LOCAL_PATH_ADAPTER_IDS = frozenset(
    {
        "file",
        "pdf",
        "pdf-markitdown",
        "pdf-marker",
        "pdf-mineru",
        "convo",
    }
)


def adapter_map() -> dict[str, type[Adapter]]:
    return {cls.id: cls for cls in ADAPTERS}


def get_adapter(adapter_id: str) -> Adapter | None:
    cls = adapter_map().get(adapter_id)
    return cls() if cls else None


def run_ingest(
    vault: Path,
    cfg: dict[str, Any],
    adapter_id: str,
    argv: list[str],
    *,
    force_adapter: bool = False,
) -> IngestResult:
    if not force_adapter and not integration_enabled(cfg, adapter_id):
        raise SystemExit(
            f"Adapter '{adapter_id}' is disabled in config.json integrations.{adapter_id}.enabled"
        )
    ad = get_adapter(adapter_id)
    if not ad:
        raise SystemExit(f"Unknown adapter: {adapter_id}. Try: llm-wiki ingest --list")
    slice_ = integration_config(cfg, adapter_id)
    warnings = type(ad).setup_checks(slice_)
    if warnings:
        print("Warnings:", *warnings, sep="\n  - ", end="\n")
    return ad.run(vault, cfg, argv)
