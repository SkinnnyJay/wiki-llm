from __future__ import annotations

import json
import os
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, ClassVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lib.paths import raw_destination
from ingest.base import Adapter, IngestResult


class FirecrawlAdapter(Adapter):
    id: ClassVar[str] = "firecrawl"
    label: ClassVar[str] = "Scrape URL via Firecrawl API (requires FIRECRAWL_API_KEY)"

    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "api_key_env": "FIRECRAWL_API_KEY",
    }

    @classmethod
    def setup_checks(cls, cfg_slice: dict[str, Any]) -> list[str]:
        env = cfg_slice.get("api_key_env") or "FIRECRAWL_API_KEY"
        if not os.environ.get(env):
            return [f"Set {env} for Firecrawl"]
        return []

    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        slice_ = cfg.get("integrations", {}).get("firecrawl") or {}
        env_name = slice_.get("api_key_env") or "FIRECRAWL_API_KEY"
        api_key = os.environ.get(env_name)
        if not api_key:
            raise SystemExit(f"Missing {env_name}")
        p = ArgumentParser(prog="llm-wiki ingest firecrawl")
        p.add_argument("url")
        p.add_argument("--out", type=Path)
        ns = p.parse_args(argv)
        base = slice_.get("api_base_url") or "https://api.firecrawl.dev"
        payload = json.dumps({"url": ns.url, "formats": ["markdown"]}).encode()
        req = Request(
            f"{base.rstrip('/')}/v1/scrape",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "llm-wiki/0.1",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode())
        except (HTTPError, URLError) as e:
            raise SystemExit(f"Firecrawl request failed: {e}") from e
        md = data.get("data", {}).get("markdown") or json.dumps(data, indent=2)
        dest = raw_destination(vault, ns.out or Path("firecrawl/page.md"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(f"# {ns.url}\n\n{md}\n", encoding="utf-8")
        return IngestResult(dest, f"Wrote {dest.relative_to(vault)}")
