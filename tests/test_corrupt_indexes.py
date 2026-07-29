"""Fail-closed corrupt JSON index behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.json_index import CorruptIndexError, load_json_object, quarantine_corrupt
from lib.knowledge_graph import JSONFileKG


def test_quarantine_corrupt_json(tmp_path: Path) -> None:
    p = tmp_path / ".kg.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(CorruptIndexError):
        load_json_object(p)
    assert not p.exists()
    corrupt = list(tmp_path.glob(".kg.json.corrupt.*"))
    assert len(corrupt) == 1


def test_kg_does_not_wipe_corrupt(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    kg_path = vault / ".kg.json"
    kg_path.write_text('{"entities":{},"triples":[{"id":"x"}]}', encoding="utf-8")
    # Corrupt after valid write
    kg_path.write_text("CORRUPT{{{", encoding="utf-8")
    kg = JSONFileKG(vault)
    with pytest.raises(CorruptIndexError):
        kg.add_triple("a", "b", "c")
    # Original corrupt content preserved in quarantine, not overwritten as empty
    assert not kg_path.exists() or kg_path.read_text(encoding="utf-8").startswith("CORRUPT")
    assert list(vault.glob(".kg.json.corrupt.*"))


def test_dedup_corrupt_raises(tmp_path: Path) -> None:
    from ingest.dedup import _load_index

    vault = tmp_path / "v"
    (vault / "raw").mkdir(parents=True)
    idx = vault / "raw" / ".hashes.json"
    idx.write_text("not-json", encoding="utf-8")
    with pytest.raises(CorruptIndexError):
        _load_index(vault)
    assert list((vault / "raw").glob(".hashes.json.corrupt.*"))


def test_layers_corrupt_tags_raises(tmp_path: Path) -> None:
    from lib.layers import _load_tags_index

    vault = tmp_path / "v"
    (vault / "raw").mkdir(parents=True)
    (vault / "raw" / ".tags.json").write_text("NOT JSON", encoding="utf-8")
    with pytest.raises(CorruptIndexError):
        _load_tags_index(vault)
    assert list((vault / "raw").glob(".tags.json.corrupt.*"))
