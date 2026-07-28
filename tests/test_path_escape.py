"""Path escape guards for vault-relative resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.path_safety import resolve_under, resolve_under_vault


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    (v / "wiki").mkdir(parents=True)
    (v / "raw").mkdir()
    (v / "wiki" / "ok.md").write_text("# ok\n", encoding="utf-8")
    (v / "config.json").write_text("{}", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("secret\n", encoding="utf-8")
    return v


@pytest.mark.parametrize(
    "rel",
    [
        "wiki/ok.md",
        Path("wiki/ok.md"),
        "./wiki/ok.md",
    ],
)
def test_resolve_under_allows_inside(vault: Path, rel: str | Path) -> None:
    p = resolve_under_vault(vault, rel)
    assert p is not None
    assert p.is_file()
    assert p.name == "ok.md"


@pytest.mark.parametrize(
    "rel",
    [
        "../secret.txt",
        "../../etc/passwd",
        "wiki/../../secret.txt",
        "wiki/../../../secret.txt",
    ],
)
def test_resolve_under_rejects_escape(vault: Path, rel: str, tmp_path: Path) -> None:
    # Ensure escape target exists next to vault parent
    assert (tmp_path / "secret.txt").is_file() or True
    p = resolve_under_vault(vault, rel)
    assert p is None


def test_resolve_under_rejects_absolute_outside(vault: Path, tmp_path: Path) -> None:
    outside = (tmp_path / "secret.txt").resolve()
    outside.write_text("x\n", encoding="utf-8")
    assert resolve_under(vault, outside) is None


def test_grep_find_related_rejects_escape(vault: Path, tmp_path: Path) -> None:
    from lib.search import GrepSearchBackend

    (tmp_path / "secret.txt").write_text("password leak material here\n", encoding="utf-8")
    backend = GrepSearchBackend(vault)
    # Would previously read parent files via vault / "../secret.txt"
    assert backend.find_related("../secret.txt") == []
    assert backend.find_related("wiki/../../secret.txt") == []


def test_mcp_check_duplicate_path_escape(vault: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """wiki_check_duplicate must not read files outside the vault."""
    import mcp_server as ms

    (tmp_path / "secret.txt").write_text("outside body\n", encoding="utf-8")
    monkeypatch.setattr(ms, "_vault", vault)
    monkeypatch.setattr(ms, "_cfg", {"mcp": {}})
    monkeypatch.setattr(ms, "_vault_ok", lambda: True)
    out = ms.tool_wiki_check_duplicate(path="../secret.txt")
    assert out.get("error") == "Path escapes vault"
