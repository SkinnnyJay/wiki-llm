from __future__ import annotations

import html
import re
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, ClassVar
from urllib.error import URLError

from lib.paths import raw_destination
from lib.url_safety import DEFAULT_MAX_BYTES, safe_fetch
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
        try:
            max_bytes = (cfg.get("ingestion") or {}).get("max_download_bytes")
            raw_body, final_url, ct = safe_fetch(
                ns.url,
                context="ingest url",
                max_bytes=max_bytes if isinstance(max_bytes, int) and max_bytes > 0 else DEFAULT_MAX_BYTES,
            )
        except URLError as e:
            raise SystemExit(f"Fetch failed: {e}") from e
        body = raw_body.decode("utf-8", errors="replace")
        if ns.out:
            dest = raw_destination(vault, ns.out)
        else:
            from urllib.parse import urlparse

            slug = urlparse(final_url).netloc.replace(":", "_") + ".md"
            dest = raw_destination(vault, Path("url") / slug)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if "html" in ct.lower():
            text = _strip_html(body)
            md = f"# Source\n\nURL: {final_url}\n\n---\n\n{text}\n"
        else:
            md = f"# Source\n\nURL: {final_url}\n\n---\n\n{body}\n"
        dest.write_text(md, encoding="utf-8")
        return IngestResult(dest, f"Wrote {dest.relative_to(vault)}")
