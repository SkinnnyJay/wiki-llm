"""Resolve paths that must stay under a vault (or other) root."""

from __future__ import annotations

from pathlib import Path


def resolve_under(root: Path, relative: str | Path) -> Path | None:
    """
    Resolve ``root / relative`` and ensure the result stays under ``root``.

    Returns the resolved Path on success, or None if the path escapes the root
    (including absolute ``relative`` that points outside root).
    """
    root_r = root.resolve()
    rel = Path(relative)
    # Absolute paths are only OK if they already live under root.
    if rel.is_absolute():
        full = rel.resolve()
    else:
        full = (root_r / rel).resolve()
    try:
        full.relative_to(root_r)
    except ValueError:
        return None
    return full


def resolve_under_vault(vault: Path, relative: str | Path) -> Path | None:
    """Alias for resolve_under(vault, …)."""
    return resolve_under(vault, relative)
