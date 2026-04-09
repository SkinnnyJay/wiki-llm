from __future__ import annotations

import html
import re
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, ClassVar
from urllib.error import URLError
from urllib.request import Request, urlopen

from lib.paths import raw_destination
from lib.url_safety import validate_public_http_url
from ingest.base import Adapter, IngestResult


def _strip_html(s: str) -> str:
    s = re.sub(r"(?is)<script.*?>.*?</script>", "", s)
    s = re.sub(r"(?is)<style.*?>.*?</style>", "", s)
    s = re.sub(r"<[^>]+>", "\n", s)
    return html.unescape(re.sub(r"\n{3,}", "\n\n", s)).strip()


class UrlAdapter(Adapter):
    id: ClassVar[str] = "url"
    label: ClassVar[str] = "Fetch URL to markdown-ish text in raw/"
    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "integration_keys": [],
        "notes": "Stdlib urllib; respect robots.txt and site terms; set a polite User-Agent.",
    }

    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        p = ArgumentParser(prog="llm-wiki ingest url")
        p.add_argument("url")
        p.add_argument("--out", type=Path, help="Relative path under raw/ e.g. clips/page.md")
        ns = p.parse_args(argv)
        validate_public_http_url(ns.url, context="ingest url")
        req = Request(ns.url, headers={"User-Agent": "llm-wiki/0.1 (+https://github.com/SkinnnyJay/wiki-llm)"})
        try:
            with urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                ct = resp.headers.get("Content-Type", "")
        except URLError as e:
            raise SystemExit(f"Fetch failed: {e}") from e
        if ns.out:
            dest = raw_destination(vault, ns.out)
        else:
            from urllib.parse import urlparse

            slug = urlparse(ns.url).netloc.replace(":", "_") + ".md"
            dest = raw_destination(vault, Path("url") / slug)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if "html" in ct.lower():
            text = _strip_html(body)
            md = f"# Source\n\nURL: {ns.url}\n\n---\n\n{text}\n"
        else:
            md = f"# Source\n\nURL: {ns.url}\n\n---\n\n{body}\n"
        dest.write_text(md, encoding="utf-8")
        return IngestResult(dest, f"Wrote {dest.relative_to(vault)}")
