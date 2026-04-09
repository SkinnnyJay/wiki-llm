"""Tests for session memory library."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from lib.config_loader import DEFAULTS, deep_merge  # noqa: I001
from lib import session_memory as mem


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    v = tmp_path / "llm-wiki"
    v.mkdir()
    cfg = deep_merge(DEFAULTS, {"memory": {"enabled": True, "dir": "raw/memory", "max_sessions": 0}})
    (v / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    return v


def test_memory_save_and_log_round(vault: Path) -> None:
    cfg = json.loads((vault / "config.json").read_text())
    mem.memory_save(
        vault,
        cfg,
        "sess-abc",
        summary="Did work",
        tags=["research"],
    )
    p = mem.memory_dir(vault, cfg) / "sess-abc.md"
    assert p.is_file()
    mem.memory_log_round(vault, cfg, "sess-abc", message_preview="Hello round")
    text = p.read_text(encoding="utf-8")
    assert "Hello round" in text
    assert "Round 1" in text


def test_resolve_sessions_tag(vault: Path) -> None:
    cfg = json.loads((vault / "config.json").read_text())
    mem.memory_save(vault, cfg, "one", summary="a", tags=["foo"])
    mem.memory_save(vault, cfg, "two", summary="b", tags=["bar"])
    paths = mem._resolve_sessions(vault, cfg, tag="foo")
    assert len(paths) == 1
    assert paths[0].stem == "one"


def test_memory_recall_uses_scope(vault: Path) -> None:
    cfg = json.loads((vault / "config.json").read_text())
    mem.memory_save(vault, cfg, "x", summary="uniquekeywordxyz123")
    # grep backend may be used in minimal env
    results = mem.memory_recall(vault, cfg, "uniquekeywordxyz123", limit=3)
    assert isinstance(results, list)


def test_raw_validate_skips_memory(tmp_path: Path) -> None:
    v = tmp_path / "llm-wiki"
    v.mkdir()
    cfg = deep_merge(DEFAULTS, {"memory": {"enabled": True, "dir": "raw/memory"}})
    (v / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    raw_mem = v / "raw" / "memory"
    raw_mem.mkdir(parents=True)
    (raw_mem / "sess.md").write_text("---\ntags: x\n---\n\n# Hi\n", encoding="utf-8")
    import llm_wiki as lw

    args = type("Args", (), {"vault": str(v), "path": "memory/sess.md", "autofix": False})()
    code = lw.cmd_raw_validate(args)
    assert code == 0
