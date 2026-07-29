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


def _patch_mcp_vault(monkeypatch: pytest.MonkeyPatch, vault: Path, cfg: dict) -> None:
    """Point MCP runtime at a test vault (state lives in mcp.ctx)."""
    import mcp.ctx as ctx
    import mcp_server as ms

    monkeypatch.setattr(ctx, "_vault", vault)
    monkeypatch.setattr(ctx, "_cfg", cfg)
    monkeypatch.setattr(ms, "_vault", vault)
    monkeypatch.setattr(ms, "_cfg", cfg)


def test_mcp_check_duplicate_path_escape(vault: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """wiki_check_duplicate must not read files outside the vault."""
    import mcp_server as ms

    (tmp_path / "secret.txt").write_text("outside body\n", encoding="utf-8")
    _patch_mcp_vault(monkeypatch, vault, {"mcp": {}})
    out = ms.tool_wiki_check_duplicate(path="../secret.txt")
    assert out.get("error") == "Path escapes vault"


def test_configure_denies_memory_dir_escape(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import mcp_server as ms

    _patch_mcp_vault(monkeypatch, vault, {"mcp": {"configure_allowlist": []}})
    out = ms.tool_wiki_configure("memory.dir", '"../../.ssh"')
    assert out.get("success") is False
    assert "not allowed" in str(out.get("error", "")).lower()


def test_configure_denies_storage_keys(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import mcp_server as ms

    _patch_mcp_vault(monkeypatch, vault, {"mcp": {"configure_allowlist": []}})
    out = ms.tool_wiki_configure("storage.search_db", '"../evil.db"')
    assert out.get("success") is False


def test_memory_dir_rejects_escape(vault: Path) -> None:
    from lib.session_memory import memory_dir

    with pytest.raises(ValueError, match="escapes"):
        memory_dir(vault, {"memory": {"dir": "../../.ssh"}})


def test_resolve_storage_rejects_escape(vault: Path) -> None:
    from lib.config_loader import resolve_storage_path

    with pytest.raises(ValueError, match="escapes"):
        resolve_storage_path(vault, {"storage": {"search_db": "../evil.db"}}, "search_db")


def test_mcp_file_ingest_gated(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import mcp_server as ms

    _patch_mcp_vault(
        monkeypatch,
        vault,
        {"mcp": {"ingest_enabled": True, "allow_local_file_ingest": False}},
    )
    out = ms.tool_wiki_ingest(adapter="file", source="/etc/passwd")
    assert out.get("success") is False
    assert "allow_local_file_ingest" in str(out.get("error", ""))


@pytest.mark.parametrize(
    "adapter",
    ["pdf", "pdf-markitdown", "pdf-marker", "pdf-mineru", "convo"],
)
def test_mcp_local_path_adapters_gated(
    vault: Path, monkeypatch: pytest.MonkeyPatch, adapter: str
) -> None:
    import mcp_server as ms

    _patch_mcp_vault(
        monkeypatch,
        vault,
        {"mcp": {"ingest_enabled": True, "allow_local_file_ingest": False}},
    )
    out = ms.tool_wiki_ingest(adapter=adapter, source="/tmp/local.pdf")
    assert out.get("success") is False
    assert "allow_local_file_ingest" in str(out.get("error", ""))


def test_configure_denies_hooks_sound(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import mcp_server as ms

    _patch_mcp_vault(monkeypatch, vault, {"mcp": {"configure_allowlist": []}})
    out = ms.tool_wiki_configure("hooks.sound.allow_arbitrary_command", "true")
    assert out.get("success") is False
    assert "not allowed" in str(out.get("error", "")).lower()


def test_wiki_read_page_denies_config(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import mcp_server as ms

    _patch_mcp_vault(monkeypatch, vault, {"mcp": {}})
    (vault / "config.json").write_text('{"mcp":{"sse_token":"secret"}}\n', encoding="utf-8")
    out = ms.tool_wiki_read_page("config.json")
    assert "error" in out
    assert "wiki/" in str(out.get("error", "")).lower() or "refusing" in str(
        out.get("error", "")
    ).lower()
