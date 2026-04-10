"""Tests for scripts/lib/config_loader.py helpers."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.config_loader import storage_warnings


def test_storage_warnings_empty_when_relative_paths(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    cfg = {"storage": {"chromadb_dir": ".chromadb"}}
    assert storage_warnings(vault, cfg) == []


def test_storage_warnings_flags_absolute_outside_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "shared"
    outside.mkdir()
    cfg = {"storage": {"chromadb_dir": str(outside / "chroma")}}
    w = storage_warnings(vault, cfg)
    assert len(w) == 1
    assert "chromadb_dir" in w[0]
    assert "outside the vault" in w[0]


def test_storage_warnings_no_warning_when_absolute_under_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    cfg = {"storage": {"chromadb_dir": str(vault / "subdir" / ".chroma")}}
    assert storage_warnings(vault, cfg) == []
