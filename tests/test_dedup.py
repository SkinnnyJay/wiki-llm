import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from ingest.dedup import (
    check_duplicate,
    content_hash,
    rebuild_index,
    register_hash,
    strip_llm_wiki_keys,
)


def test_strip_removes_llm_wiki_keys_from_combined_frontmatter():
    body = "---\ntitle: Auth\nllm_wiki_tags: [auth]\nllm_wiki_content_hash: sha256:abc\n---\n\n# Auth\n\nContent."
    result = strip_llm_wiki_keys(body)
    assert "llm_wiki_tags" not in result
    assert "llm_wiki_content_hash" not in result
    assert "title: Auth" in result
    assert "# Auth" in result

def test_strip_removes_separate_llm_wiki_block():
    body = "---\ntitle: Auth\n---\n---\nllm_wiki_tags: [auth]\n---\n\n# Auth\n"
    result = strip_llm_wiki_keys(body)
    assert "llm_wiki_tags" not in result
    assert "title: Auth" in result

def test_strip_removes_nested_llm_wiki_keys():
    # llm_wiki_security has indented child lines
    body = (
        "---\ntitle: Auth\n"
        "llm_wiki_security:\n"
        "  prompt_injection: 'low_risk'\n"
        "  signals: []\n"
        "llm_wiki_tags: [auth]\n"
        "---\n\n# Auth\n"
    )
    result = strip_llm_wiki_keys(body)
    assert "llm_wiki_security" not in result
    assert "prompt_injection" not in result
    assert "llm_wiki_tags" not in result
    assert "title: Auth" in result
    body = "---\ntitle: Auth\nllm_wiki_tags: [auth]\n---\n\n# Content"
    assert strip_llm_wiki_keys(strip_llm_wiki_keys(body)) == strip_llm_wiki_keys(body)

def test_content_hash_stable_across_tag_changes():
    body1 = "---\ntitle: Auth\nllm_wiki_tags: [auth]\n---\n\n# Content"
    body2 = "---\ntitle: Auth\nllm_wiki_tags: [auth, billing]\n---\n\n# Content"
    assert content_hash(body1) == content_hash(body2)

def test_content_hash_differs_for_different_content():
    assert content_hash("# A\nfoo") != content_hash("# B\nbar")

def test_hash_format():
    h = content_hash("hello")
    assert h.startswith("sha256:")
    assert len(h) == 7 + 64  # "sha256:" + 64 hex chars

def test_check_duplicate_empty_vault(tmp_path):
    assert check_duplicate(tmp_path, "sha256:abc") == []

def test_register_and_check_duplicate(tmp_path):
    register_hash(tmp_path, "sha256:abc", tmp_path / "raw" / "file.md")
    result = check_duplicate(tmp_path, "sha256:abc")
    assert len(result) == 1
    assert result[0] == tmp_path / "raw" / "file.md"

def test_register_hash_atomic(tmp_path):
    # Register twice — second write should not corrupt
    register_hash(tmp_path, "sha256:abc", tmp_path / "a.md")
    register_hash(tmp_path, "sha256:def", tmp_path / "b.md")
    assert check_duplicate(tmp_path, "sha256:abc") == [tmp_path / "a.md"]
    assert check_duplicate(tmp_path, "sha256:def") == [tmp_path / "b.md"]

def test_corrupt_hashes_json_fail_closed(tmp_path):
    from lib.json_index import CorruptIndexError

    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / ".hashes.json").write_text("NOT JSON")
    with pytest.raises(CorruptIndexError):
        check_duplicate(tmp_path, "sha256:abc")
    assert list((tmp_path / "raw").glob(".hashes.json.corrupt.*"))

def test_rebuild_index(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.md").write_text("---\nllm_wiki_content_hash: sha256:aaa\n---\n# A")
    (raw / "b.md").write_text("---\nllm_wiki_content_hash: sha256:bbb\n---\n# B")
    count = rebuild_index(tmp_path)
    assert count == 2
    assert check_duplicate(tmp_path, "sha256:aaa") == [raw / "a.md"]
