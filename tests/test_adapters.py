# tests/test_adapters.py
"""Offline-safe smoke tests for every ingest adapter (id/label, setup_checks, clean exits)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from ingest.adapters import ADAPTERS  # noqa: E402
from lib.config_loader import DEFAULTS  # noqa: E402


def _vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    v.mkdir()
    (v / "raw").mkdir()
    return v


def _cfg() -> dict[str, Any]:
    return dict(DEFAULTS)


def _run_bad_args(adapter_cls: type, argv: list[str], tmp_path: Path) -> None:
    """Adapter.run must exit via SystemExit (or argparse), not an unhandled exception."""
    inst = adapter_cls()
    vault = _vault(tmp_path)
    with pytest.raises(SystemExit):
        inst.run(vault, _cfg(), argv)


@pytest.mark.parametrize("adapter_cls", ADAPTERS, ids=lambda c: c.id)
def test_adapter_id_label_and_setup_checks(adapter_cls: type) -> None:
    assert isinstance(adapter_cls.id, str) and adapter_cls.id
    assert isinstance(adapter_cls.label, str) and adapter_cls.label
    warns = adapter_cls.setup_checks({})
    assert isinstance(warns, list)
    assert all(isinstance(w, str) for w in warns)


def test_file_adapter_missing_source_exits(tmp_path: Path) -> None:
    from ingest.adapters.file import FileAdapter

    _run_bad_args(FileAdapter, ["/no/such/file.md"], tmp_path)


def test_url_adapter_invalid_scheme_exits(tmp_path: Path) -> None:
    from ingest.adapters.url import UrlAdapter

    _run_bad_args(UrlAdapter, ["file:///etc/passwd"], tmp_path)


def test_hackernews_adapter_unknown_arg_exits(tmp_path: Path) -> None:
    from ingest.adapters.hackernews import HackerNewsAdapter

    _run_bad_args(HackerNewsAdapter, ["--not-a-real-flag"], tmp_path)


def test_pdf_vision_setup_warns_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """When pdf2image, anthropic, and poppler look OK, missing API key yields a clear warning."""
    import ingest.adapters.pdf_vision as pv

    monkeypatch.setattr(pv, "_has_pdf2image", lambda: True)
    monkeypatch.setattr(pv, "_has_anthropic", lambda: True)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def _which(cmd: str) -> str | None:
        return "/fake/pdftoppm" if cmd == "pdftoppm" else shutil.which(cmd)

    monkeypatch.setattr(pv.shutil, "which", _which)

    from ingest.adapters.pdf_vision import PdfVisionAdapter

    warns = PdfVisionAdapter.setup_checks({})
    assert warns and "ANTHROPIC_API_KEY" in warns[0]


def test_pdf_vision_preflight_or_missing_file_exits(tmp_path: Path) -> None:
    from ingest.adapters.pdf_vision import PdfVisionAdapter

    fake = tmp_path / "nope.pdf"
    _run_bad_args(PdfVisionAdapter, [str(fake)], tmp_path)


def test_pdf_marker_preflight_exits(tmp_path: Path) -> None:
    from ingest.adapters.pdf_marker import PdfMarkerAdapter

    fake = tmp_path / "nope.pdf"
    _run_bad_args(PdfMarkerAdapter, [str(fake)], tmp_path)


def test_pdf_markitdown_preflight_or_missing_file_exits(tmp_path: Path) -> None:
    from ingest.adapters.pdf_markitdown import PdfMarkitdownAdapter

    fake = tmp_path / "nope.pdf"
    _run_bad_args(PdfMarkitdownAdapter, [str(fake)], tmp_path)


def test_pdf_mineru_preflight_exits(tmp_path: Path) -> None:
    from ingest.adapters.pdf_mineru import PdfMineruAdapter

    fake = tmp_path / "nope.pdf"
    _run_bad_args(PdfMineruAdapter, [str(fake)], tmp_path)


def test_firecrawl_setup_warns_without_key_or_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    from ingest.adapters.web_firecrawl import FirecrawlAdapter

    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    def _which(cmd: str) -> str | None:
        return None if cmd == "firecrawl" else shutil.which(cmd)

    monkeypatch.setattr("ingest.adapters.web_firecrawl.shutil.which", _which)
    warns = FirecrawlAdapter.setup_checks({})
    assert warns


def test_firecrawl_bad_url_exits(tmp_path: Path) -> None:
    from ingest.adapters.web_firecrawl import FirecrawlAdapter

    _run_bad_args(FirecrawlAdapter, [""], tmp_path)


def test_youtube_import_or_parse_exits(tmp_path: Path) -> None:
    from ingest.adapters.youtube import YoutubeAdapter

    try:
        import youtube_transcript_api  # noqa: F401
    except ImportError:
        _run_bad_args(YoutubeAdapter, ["dQw4w9WgXcQ"], tmp_path)
    else:
        _run_bad_args(YoutubeAdapter, ["--not-a-real-flag"], tmp_path)


def test_perplexity_setup_warns_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from ingest.adapters.perplexity import PerplexityAdapter

    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    warns = PerplexityAdapter.setup_checks({})
    assert warns and "PERPLEXITY" in warns[0].upper()


def test_perplexity_missing_key_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ingest.adapters.perplexity import PerplexityAdapter

    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    _run_bad_args(PerplexityAdapter, ["hello"], tmp_path)


def test_twitter_setup_warns_without_bird_or_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from ingest.adapters.twitter import TwitterAdapter

    monkeypatch.delenv("TWITTER_AUTH_TOKEN", raising=False)

    def _which(cmd: str) -> str | None:
        return None if cmd == "bird" else shutil.which(cmd)

    monkeypatch.setattr("ingest.adapters.twitter.shutil.which", _which)
    warns = TwitterAdapter.setup_checks({})
    assert isinstance(warns, list) and warns


def test_twitter_no_subcommand_exits(tmp_path: Path) -> None:
    from ingest.adapters.twitter import TwitterAdapter

    _run_bad_args(TwitterAdapter, [], tmp_path)


def test_twitter_bare_id_exits(tmp_path: Path) -> None:
    from ingest.adapters.twitter import TwitterAdapter

    _run_bad_args(TwitterAdapter, ["1234567890123456789"], tmp_path)


def test_brave_setup_warns_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from ingest.adapters.brave_search import BraveSearchAdapter

    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    warns = BraveSearchAdapter.setup_checks({})
    assert warns and "BRAVE" in warns[0].upper()


def test_brave_missing_key_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ingest.adapters.brave_search import BraveSearchAdapter

    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    _run_bad_args(BraveSearchAdapter, ["test query"], tmp_path)
