# tests/test_layers.py
import json
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from lib.layers import build_wake_up, update_claude_md

def _make_vault(tmp_path):
    vault = tmp_path / "v"
    (vault / "raw").mkdir(parents=True)
    (vault / "wiki").mkdir()
    (vault / "raw" / ".tags.json").write_text(json.dumps({
        "auth": ["raw/a.md", "raw/b.md"],
        "billing": ["raw/c.md"],
    }))
    (vault / "wiki" / "auth.md").write_text("# Auth\n")
    (vault / "wiki" / "log.md").write_text(
        "- [2026-04-05] first entry\n- [2026-04-04] second\n"
    )
    return vault, {"persona": {"name": "TestBot"}, "version": "0.1.13"}

def test_wake_up_contains_vault_name(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    out = build_wake_up(vault, cfg)
    assert "TestBot" in out

def test_wake_up_shows_topics(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    out = build_wake_up(vault, cfg)
    assert "auth" in out
    assert "billing" in out

def test_wake_up_shows_wiki_coverage(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    out = build_wake_up(vault, cfg)
    assert "✓" in out or "wiki/auth.md" in out  # auth has a wiki page
    assert "⚠" in out or "no wiki" in out.lower()  # billing does not

def test_wake_up_handles_missing_log(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    (vault / "wiki" / "log.md").unlink()
    out = build_wake_up(vault, cfg)
    assert "TestBot" in out  # still works

def test_wake_up_handles_no_tags(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    (vault / "raw" / ".tags.json").unlink()
    out = build_wake_up(vault, cfg)
    assert "none yet" in out.lower() or "Topics:" in out

def test_update_claude_md_creates_section(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    claude_md = tmp_path / "v" / "CLAUDE.md"
    claude_md.write_text("# Vault\n\n## On query\n\nAnswer.\n")
    update_claude_md(vault, cfg)
    text = claude_md.read_text()
    assert "## Memory Stack" in text
    assert "auth" in text

def test_update_claude_md_replaces_existing_section(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    claude_md = tmp_path / "v" / "CLAUDE.md"
    claude_md.write_text("# Vault\n\n## Memory Stack\n\nOLD CONTENT\n\n## On query\n\nAnswer.\n")
    update_claude_md(vault, cfg)
    text = claude_md.read_text()
    assert "OLD CONTENT" not in text
    assert text.count("## Memory Stack") == 1

def test_update_claude_md_missing_file_is_noop(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    # No CLAUDE.md exists
    update_claude_md(vault, cfg)  # should not raise
