# tests/test_tagger.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from ingest.tagger import detect_tags, merge_tags, rebuild_tag_index, register_tags


def test_detect_tags_from_path():
    result = detect_tags("# Some content", Path("raw/auth/decision.md"), {})
    assert "auth" in result.tags


def test_detect_tags_from_h1():
    result = detect_tags("# Auth Migration Decision\n\nContent.", Path("raw/note.md"), {})
    assert "auth" in result.tags
    assert "migration" in result.tags

def test_detect_tags_from_obsidian_frontmatter():
    body = "---\ntitle: Note\ntags: [auth, billing]\n---\n\n# Content"
    result = detect_tags(body, Path("raw/note.md"), {})
    assert "auth" in result.tags
    assert "billing" in result.tags

def test_detect_tags_source_is_auto():
    result = detect_tags("# Auth\nContent", Path("raw/note.md"), {})
    assert result.source == "auto"

def test_merge_manual_overrides():
    result = merge_tags(auto=["auth"], manual=["billing"], llm=[])
    assert "billing" in result.tags
    assert "auto+manual" == result.source

def test_merge_source_sorted():
    result = merge_tags(auto=["auth"], manual=["x"], llm=["y"])
    assert result.source == "auto+llm+manual"

def test_merge_deduplicates():
    result = merge_tags(auto=["auth", "auth"], manual=["auth"], llm=[])
    assert result.tags.count("auth") == 1

def test_register_and_lookup_tags(tmp_path):
    register_tags(tmp_path, ["auth", "billing"], tmp_path / "raw" / "a.md")
    index_path = tmp_path / "raw" / ".tags.json"
    assert index_path.exists()
    data = json.loads(index_path.read_text())
    assert str(tmp_path / "raw" / "a.md") in data["auth"]
    assert str(tmp_path / "raw" / "a.md") in data["billing"]

def test_register_tags_atomic(tmp_path):
    register_tags(tmp_path, ["auth"], tmp_path / "raw" / "a.md")
    register_tags(tmp_path, ["auth"], tmp_path / "raw" / "b.md")
    data = json.loads((tmp_path / "raw" / ".tags.json").read_text())
    assert len(data["auth"]) == 2

def test_corrupt_tags_json_fail_closed(tmp_path):
    from lib.json_index import CorruptIndexError

    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / ".tags.json").write_text("NOT JSON")
    with pytest.raises(CorruptIndexError):
        register_tags(tmp_path, ["auth"], tmp_path / "raw" / "a.md")
    assert list((tmp_path / "raw").glob(".tags.json.corrupt.*"))

def test_rebuild_tag_index(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.md").write_text("---\nllm_wiki_tags: [auth, billing]\n---\n# A")
    (raw / "b.md").write_text("---\nllm_wiki_tags: [auth]\n---\n# B")
    count = rebuild_tag_index(tmp_path)
    assert count == 2
    data = json.loads((raw / ".tags.json").read_text())
    assert len(data["auth"]) == 2
    assert len(data["billing"]) == 1
