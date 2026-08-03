from __future__ import annotations

import json
import os
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, ClassVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lib.http_defaults import USER_AGENT
from lib.paths import raw_destination
from lib.url_safety import validate_https_api_host

from ingest.base import Adapter, IngestResult

_PERPLEXITY_API_HOSTS = frozenset({"api.perplexity.ai"})


class PerplexityAdapter(Adapter):
    id: ClassVar[str] = "perplexity"
    label: ClassVar[str] = "Research prompt via Perplexity Sonar API (PERPLEXITY_API_KEY)"

    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "api_key_env": "PERPLEXITY_API_KEY",
        "model": "sonar",
    }

    @classmethod
    def setup_checks(cls, cfg_slice: dict[str, Any]) -> list[str]:
        env = cfg_slice.get("api_key_env") or "PERPLEXITY_API_KEY"
        if not os.environ.get(env):
            return [f"Set {env} for Perplexity"]
        return []

    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        slice_ = cfg.get("integrations", {}).get("perplexity") or {}
        env_name = slice_.get("api_key_env") or "PERPLEXITY_API_KEY"
        api_key = os.environ.get(env_name)
        if not api_key:
            raise SystemExit(f"Missing {env_name}")
        base = validate_https_api_host(
            slice_.get("api_base_url"),
            default_host="api.perplexity.ai",
            allowed_hosts=_PERPLEXITY_API_HOSTS,
            integration_name="integrations.perplexity",
        ).rstrip("/")
        default_model = slice_.get("model") or "sonar"

        p = ArgumentParser(prog="llm-wiki ingest perplexity")
        p.add_argument(
            "prompt_parts",
            nargs="*",
            help="Prompt text (or use --prompt-file)",
        )
        p.add_argument("--prompt-file", type=Path, help="Read prompt from this file")
        p.add_argument("--out", type=Path, help="Relative path under raw/")
        p.add_argument("--model", default=None, help="Override config model (e.g. sonar-pro)")
        ns = p.parse_args(argv)
        if ns.prompt_file:
            prompt = ns.prompt_file.read_text(encoding="utf-8", errors="replace").strip()
        else:
            prompt = " ".join(ns.prompt_parts).strip()
        if not prompt:
            raise SystemExit("Provide a prompt or --prompt-file")

        model = ns.model or default_model
        payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}]}).encode()
        req = Request(
            f"{base}/v1/sonar",
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
            raise SystemExit(f"Perplexity request failed: {e}") from e

        choices = data.get("choices") or []
        if not choices:
            raise SystemExit(f"Unexpected Perplexity response (no choices): {json.dumps(data)[:500]}")
        content = (choices[0].get("message") or {}).get("content") or ""
        citations = data.get("citations") or []
        lines = [
            f"# Perplexity ({model})\n",
            f"Prompt:\n\n{prompt}\n",
            "---\n\n",
            content.strip(),
            "\n",
        ]
        if citations:
            lines.append("\n## Citations\n\n")
            for c in citations:
                lines.append(f"- {c}\n")

        stem = (ns.out and ns.out.stem) or "perplexity-query"
        dest = raw_destination(vault, ns.out or Path(f"research/{stem}.md"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("".join(lines), encoding="utf-8")
        return IngestResult(dest, f"Wrote {dest.relative_to(vault)}")
