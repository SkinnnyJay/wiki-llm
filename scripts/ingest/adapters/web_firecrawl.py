from __future__ import annotations

import json
import os
import shutil
import subprocess
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, ClassVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lib.http_defaults import USER_AGENT
from lib.paths import raw_destination
from lib.url_safety import validate_https_api_host, validate_public_http_url
from ingest.base import Adapter, IngestResult

_FIRECRAWL_API_HOSTS = frozenset({"api.firecrawl.dev"})


class FirecrawlAdapter(Adapter):
    id: ClassVar[str] = "firecrawl"
    label: ClassVar[str] = (
        "Scrape URL via Firecrawl CLI (preferred) or REST API fallback "
        "(requires FIRECRAWL_API_KEY)"
    )

    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "api_key_env": "FIRECRAWL_API_KEY",
        "api_base_url": "https://api.firecrawl.dev",
        "prefer_cli": True,
    }

    @classmethod
    def setup_checks(cls, cfg_slice: dict[str, Any]) -> list[str]:
        env = cfg_slice.get("api_key_env") or "FIRECRAWL_API_KEY"
        has_key = bool(os.environ.get(env))
        has_cli = bool(shutil.which("firecrawl"))
        if not has_key and not has_cli:
            return [f"Set {env} (REST API) or install firecrawl CLI: npm install -g firecrawl-cli"]
        return []

    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        slice_ = cfg.get("integrations", {}).get("firecrawl") or {}
        p = ArgumentParser(prog="llm-wiki ingest firecrawl")
        p.add_argument("url")
        p.add_argument("--out", type=Path)
        ns = p.parse_args(argv)
        validate_public_http_url(ns.url, context="ingest firecrawl")

        prefer_cli = slice_.get("prefer_cli", True)
        has_cli = bool(shutil.which("firecrawl"))

        if prefer_cli and has_cli:
            md = self._fetch_via_cli(ns.url)
        else:
            md = self._fetch_via_api(ns.url, slice_)

        dest = raw_destination(vault, ns.out or Path("firecrawl/page.md"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(f"# {ns.url}\n\n{md}\n", encoding="utf-8")
        return IngestResult(dest, f"Wrote {dest.relative_to(vault)}")

    def _fetch_via_cli(self, url: str) -> str:
        """Use the locally installed firecrawl CLI to scrape a URL."""
        result = subprocess.run(
            ["firecrawl", "scrape", url, "--format", "markdown"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise SystemExit(
                f"firecrawl CLI failed (rc={result.returncode}): {result.stderr.strip()}"
            )
        output = result.stdout.strip()
        if not output:
            raise SystemExit("firecrawl CLI returned empty output")
        # CLI may write JSON; if so, extract markdown field
        if output.startswith("{"):
            try:
                data = json.loads(output)
                return (
                    data.get("markdown")
                    or data.get("data", {}).get("markdown")
                    or output
                )
            except json.JSONDecodeError:
                pass
        return output

    def _fetch_via_api(self, url: str, slice_: dict[str, Any]) -> str:
        """Fall back to the Firecrawl REST API when CLI is unavailable."""
        env_name = slice_.get("api_key_env") or "FIRECRAWL_API_KEY"
        api_key = os.environ.get(env_name)
        if not api_key:
            raise SystemExit(
                f"Missing {env_name} and no firecrawl CLI found. "
                "Run: npm install -g firecrawl-cli && firecrawl login"
            )
        base = validate_https_api_host(
            slice_.get("api_base_url"),
            default_host="api.firecrawl.dev",
            allowed_hosts=_FIRECRAWL_API_HOSTS,
            integration_name="integrations.firecrawl",
        )
        payload = json.dumps({"url": url, "formats": ["markdown"]}).encode()
        req = Request(
            f"{base.rstrip('/')}/v1/scrape",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode())
        except (HTTPError, URLError) as e:
            raise SystemExit(f"Firecrawl API request failed: {e}") from e
        return data.get("data", {}).get("markdown") or json.dumps(data, indent=2)
