"""Non-destructive vault diagnostics and narrowly scoped safe repairs."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any

from lib.config_loader import DEFAULTS, merge_missing_defaults, save_config
from lib.paths import plugin_root

_SECRET_PARTS = ("secret", "token", "password", "api_key", "key_env")
_VALID_BACKENDS = {"fts5", "grep", "chromadb", "hybrid"}


def _check(name: str, status: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"name": name, "status": status, "message": message, **extra}


def _safe_default_repairs(data: dict[str, Any]) -> list[str]:
    """Replace only blank scalar config values that have non-blank defaults."""
    repaired: list[str] = []

    def visit(current: dict[str, Any], defaults: dict[str, Any], prefix: str = "") -> None:
        for key, default in defaults.items():
            path = f"{prefix}.{key}" if prefix else key
            value = current.get(key)
            if isinstance(default, dict) and isinstance(value, dict):
                visit(value, default, path)
                continue
            if (
                key in current
                and value in (None, "")
                and default not in (None, "")
                and not any(part in path.lower() for part in _SECRET_PARTS)
            ):
                current[key] = deepcopy(default)
                repaired.append(path)

    visit(data, DEFAULTS)
    return repaired


def _fts5_available() -> bool:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE pages USING fts5(content)")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def doctor_report(vault: Path, *, fix: bool = False) -> dict[str, Any]:
    """Return a JSON-serializable health report; ``fix`` makes safe repairs only."""
    checks: list[dict[str, Any]] = []
    fixes: list[str] = []
    vault = vault.resolve()

    if not vault.is_dir():
        if fix:
            vault.mkdir(parents=True, exist_ok=True)
            fixes.append("created vault directory")
        checks.append(
            _check(
                "vault",
                "ok" if vault.is_dir() else "error",
                str(vault) if vault.is_dir() else f"missing: {vault}",
            )
        )
    else:
        checks.append(_check("vault", "ok", str(vault)))

    config_path = vault / "config.json"
    config: dict[str, Any] | None = None
    if not config_path.is_file():
        checks.append(_check("config", "error", "config.json is missing; run: llm-wiki setup"))
    else:
        try:
            parsed = json.loads(config_path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("JSON root must be an object")
            config = parsed
            if fix:
                added = merge_missing_defaults(config)
                configured_version = config.get("version")
                default_version = DEFAULTS["version"]
                version_changed = configured_version != default_version
                if version_changed:
                    config["version"] = default_version
                    fixes.append(
                        f"updated config version from {configured_version!r} to {default_version!r}"
                    )
                repaired = _safe_default_repairs(config)
                if added or repaired or version_changed:
                    save_config(vault, config)
                    fixes.extend(f"added missing default for {path}" for path in added)
                    fixes.extend(f"restored default for {path}" for path in repaired)
            checks.append(_check("config", "ok", str(config_path)))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            checks.append(_check("config", "error", f"invalid config.json: {exc}"))

    for name in ("raw", "wiki"):
        path = vault / name
        if not path.is_dir() and fix:
            path.mkdir(parents=True, exist_ok=True)
            fixes.append(f"created {name}/")
        checks.append(
            _check(
                f"directory.{name}",
                "ok" if path.is_dir() else "error",
                str(path) if path.is_dir() else f"missing: {path}",
            )
        )

    if config is None:
        checks.append(_check("mcp.enabled", "warn", "not checked because config is invalid"))
        checks.append(_check("search_backend", "warn", "not checked because config is invalid"))
    else:
        mcp = config.get("mcp")
        mcp = mcp if isinstance(mcp, dict) else {}
        enabled = mcp.get("enabled", DEFAULTS["mcp"]["enabled"])
        checks.append(
            _check(
                "mcp.enabled",
                "ok" if enabled else "warn",
                f"enabled={bool(enabled)}",
            )
        )
        backend = mcp.get("search_backend", DEFAULTS["mcp"]["search_backend"])
        if backend not in _VALID_BACKENDS:
            checks.append(_check("search_backend", "error", f"unsupported backend: {backend!r}"))
        elif backend in {"chromadb", "hybrid"} and importlib.util.find_spec("chromadb") is None:
            fallback = "grep" if backend == "chromadb" else "fts5"
            checks.append(
                _check(
                    "search_backend",
                    "warn",
                    f"{backend} unavailable (chromadb not installed); falls back to {fallback}",
                    configured=backend,
                    active=fallback,
                )
            )
        elif backend in {"fts5", "hybrid"} and not _fts5_available():
            checks.append(_check("search_backend", "error", "SQLite was built without FTS5 support"))
        else:
            checks.append(_check("search_backend", "ok", f"{backend} available", configured=backend))

    quarantined = sorted(
        str(path.relative_to(vault))
        for path in vault.rglob("*.corrupt.*")
        if path.is_file()
    ) if vault.is_dir() else []
    checks.append(
        _check(
            "corrupt_indexes",
            "warn" if quarantined else "ok",
            f"{len(quarantined)} quarantined index file(s)" if quarantined else "none",
            files=quarantined,
        )
    )
    hooks_dir = plugin_root() / "hooks"
    checks.append(
        _check(
            "hooks",
            "ok" if hooks_dir.is_dir() else "warn",
            f"Optional hook scripts: {hooks_dir}; see hooks/README.md",
        )
    )

    errors = sum(check["status"] == "error" for check in checks)
    warnings = sum(check["status"] == "warn" for check in checks)
    return {
        "vault_path": str(vault),
        "ok": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "fixes": fixes,
    }
