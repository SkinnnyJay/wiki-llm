from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse

from lib.paths import raw_destination
from lib.url_safety import validate_public_http_url
from ingest.adapters.url import _strip_html
from ingest.base import Adapter, IngestResult


def _playwright_import_ok() -> bool:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return True


class PlaywrightAdapter(Adapter):
    id: ClassVar[str] = "playwright"
    label: ClassVar[str] = (
        "Fetch URL with headless Chromium (Playwright) — JS-heavy pages; "
        "requires: pip install playwright && playwright install chromium"
    )

    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "integration_keys": [],
        "notes": "Python playwright package; same raw/ markdown shape as url and firecrawl.",
    }

    @classmethod
    def setup_checks(cls, cfg_slice: dict[str, Any]) -> list[str]:
        if not _playwright_import_ok():
            return [
                "pip install playwright && playwright install chromium  "
                "(headless browser fetch; optional Playwright MCP in the editor is separate)"
            ]
        return []

    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        p = ArgumentParser(prog="llm-wiki ingest playwright")
        p.add_argument("url")
        p.add_argument("--out", type=Path)
        p.add_argument(
            "--timeout",
            type=int,
            default=90,
            metavar="SEC",
            help="Navigation timeout in seconds (default: 90)",
        )
        ns = p.parse_args(argv)
        validate_public_http_url(ns.url, context="ingest playwright")

        if not _playwright_import_ok():
            raise SystemExit(
                "Playwright is not installed. Run: pip install playwright && playwright install chromium"
            )

        from playwright.sync_api import sync_playwright

        print(f"playwright: loading {ns.url!r} ...", file=sys.stderr)
        timeout_ms = max(5_000, min(ns.timeout * 1000, 300_000))

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_default_timeout(timeout_ms)
                page.goto(ns.url, wait_until="domcontentloaded")
                title = (page.title() or "").strip() or "Source"
                html = page.content()
            finally:
                browser.close()

        text = _strip_html(html)
        if not text.strip():
            text = "(no text extracted after HTML strip — page may be empty or blocked)"

        md = f"# {title}\n\nURL: {ns.url}\n\n---\n\n{text}\n"

        if ns.out:
            dest = raw_destination(vault, ns.out)
        else:
            slug = urlparse(ns.url).netloc.replace(":", "_") + ".md"
            dest = raw_destination(vault, Path("playwright") / slug)

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md, encoding="utf-8")
        return IngestResult(dest, f"Wrote {dest.relative_to(vault)}")
