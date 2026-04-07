"""Load integration slices from vault config."""

from __future__ import annotations

from typing import Any


def integration_enabled(cfg: dict[str, Any], adapter_id: str) -> bool:
    integrations = cfg.get("integrations") or {}
    if adapter_id not in integrations:
        return True
    entry = integrations.get(adapter_id) or {}
    return bool(entry.get("enabled", True))


def integration_config(cfg: dict[str, Any], adapter_id: str) -> dict[str, Any]:
    integrations = cfg.get("integrations") or {}
    return dict(integrations.get(adapter_id) or {})
