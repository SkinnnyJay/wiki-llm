from __future__ import annotations

import json
import os
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, ClassVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from lib.http_defaults import USER_AGENT
from lib.paths import raw_destination

from ingest.base import Adapter, IngestResult

_BRAVE_API = "https://api.search.brave.com/res/v1"

# Modes exposed via --mode flag
_MODES = ("web", "news", "llm-context", "answers")


def _get(endpoint: str, params: dict, api_key: str) -> Any:
    qs = urlencode(params)
    req = Request(
        f"{_BRAVE_API}/{endpoint}?{qs}",
        headers={
            "X-Subscription-Token": api_key,
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except (HTTPError, URLError) as e:
        raise SystemExit(f"Brave Search API error ({endpoint}): {e}") from e


def _post(endpoint: str, payload: dict, api_key: str) -> Any:
    body = json.dumps(payload).encode()
    req = Request(
        f"{_BRAVE_API}/{endpoint}",
        data=body,
        headers={
            "X-Subscription-Token": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except (HTTPError, URLError) as e:
        raise SystemExit(f"Brave Search API error ({endpoint}): {e}") from e


def _format_web(data: dict, query: str, count: int) -> str:
    results = (data.get("web") or {}).get("results") or []
    lines = [f"# Brave Web Search\n\nQuery: `{query}`  Count: {count}\n\n---\n"]
    for r in results:
        title = r.get("title") or "(no title)"
        url = r.get("url") or ""
        desc = r.get("description") or ""
        age = r.get("age") or ""
        lines.append(f"## {title}\n\n- URL: {url}\n- Age: {age}\n\n{desc}\n")
        for snip in r.get("extra_snippets") or []:
            lines.append(f"> {snip}\n")
        lines.append("")
    return "\n".join(lines)


def _format_news(data: dict, query: str, count: int) -> str:
    results = (data.get("news") or {}).get("results") or []
    lines = [f"# Brave News Search\n\nQuery: `{query}`  Count: {count}\n\n---\n"]
    for r in results:
        title = r.get("title") or "(no title)"
        url = r.get("url") or ""
        desc = r.get("description") or ""
        age = r.get("age") or ""
        src = (r.get("meta_url") or {}).get("hostname") or ""
        lines.append(f"## {title}\n\n- Source: {src}  Age: {age}\n- URL: {url}\n\n{desc}\n\n")
    return "\n".join(lines)


def _format_llm_context(data: dict, query: str) -> str:
    """LLM-context endpoint returns pre-extracted page content — best for RAG grounding."""
    results = data.get("results") or []
    lines = [
        f"# Brave LLM Context\n\nQuery: `{query}`\n",
        "*Pre-extracted web content optimised for LLM grounding.*\n\n---\n",
    ]
    for r in results:
        title = r.get("title") or "(no title)"
        url = r.get("url") or ""
        content = r.get("content") or r.get("description") or ""
        age = r.get("age") or ""
        lines.append(f"## {title}\n\n- URL: {url}  Age: {age}\n\n{content}\n\n---\n")
    return "\n".join(lines)


def _format_answers(data: dict, query: str) -> str:
    """AI-grounded answer from Brave Answers endpoint (OpenAI-compatible response)."""
    choices = data.get("choices") or []
    content = ""
    if choices:
        content = (choices[0].get("message") or {}).get("content") or ""
    citations = data.get("citations") or []
    lines = [f"# Brave Answers\n\nQuery: `{query}`\n\n---\n\n{content.strip()}\n"]
    if citations:
        lines.append("\n## Citations\n")
        for c in citations:
            lines.append(f"- {c}")
    return "\n".join(lines) + "\n"


class BraveSearchAdapter(Adapter):
    """
    Search the web via Brave Search API.

    Modes:
      web          Ranked web results with snippets (default)
      news         News articles with freshness filtering
      llm-context  Pre-extracted page content optimised for LLM RAG grounding
      answers      AI-grounded answer with citations (OpenAI SDK compatible)

    Requires: BRAVE_SEARCH_API_KEY
    Get a free key: https://api.search.brave.com
    """

    id: ClassVar[str] = "brave"
    label: ClassVar[str] = (
        "Brave Search API — web/news/llm-context/answers modes (BRAVE_SEARCH_API_KEY)"
    )
    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "api_key_env": "BRAVE_SEARCH_API_KEY",
        "default_mode": "llm-context",
        "default_count": 10,
        "_notes": "Get free key: https://api.search.brave.com  Modes: web | news | llm-context | answers",
    }

    @classmethod
    def setup_checks(cls, cfg_slice: dict[str, Any]) -> list[str]:
        env = cfg_slice.get("api_key_env") or "BRAVE_SEARCH_API_KEY"
        if not os.environ.get(env):
            return [f"Set {env}  (free key: https://api.search.brave.com)"]
        return []

    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        slice_ = (cfg.get("integrations") or {}).get("brave") or {}
        env_name = slice_.get("api_key_env") or "BRAVE_SEARCH_API_KEY"
        api_key = os.environ.get(env_name)
        if not api_key:
            raise SystemExit(
                f"Missing {env_name}. Get a free key at https://api.search.brave.com "
                "then: llm-wiki integrations set-key brave <key>"
            )

        default_mode = slice_.get("default_mode") or "llm-context"
        default_count = int(slice_.get("default_count") or 10)

        p = ArgumentParser(prog="llm-wiki ingest brave")
        p.add_argument("query_parts", nargs="*", help="Search query words")
        p.add_argument("--query", "-q", help="Search query (alternative to positional)")
        p.add_argument(
            "--mode",
            choices=_MODES,
            default=default_mode,
            help=f"API mode (default: {default_mode})",
        )
        p.add_argument(
            "--count",
            type=int,
            default=default_count,
            help=f"Number of results (default: {default_count})",
        )
        p.add_argument("--freshness", help="Date filter, e.g. pd (past day), pw, pm, py")
        p.add_argument("--goggles", help="Brave Goggles URL or inline goggle for custom ranking")
        p.add_argument("--out", type=Path, help="Output path under raw/")
        ns = p.parse_args(argv)

        query = ns.query or " ".join(ns.query_parts).strip()
        if not query:
            p.error("Provide a search query")

        mode = ns.mode
        md: str
        if mode == "web":
            params: dict = {"q": query, "count": ns.count}
            if ns.freshness:
                params["freshness"] = ns.freshness
            if ns.goggles:
                params["goggles"] = ns.goggles
            data = _get("web/search", params, api_key)
            md = _format_web(data, query, ns.count)
        elif mode == "news":
            params = {"q": query, "count": ns.count}
            if ns.freshness:
                params["freshness"] = ns.freshness
            data = _get("news/search", params, api_key)
            md = _format_news(data, query, ns.count)
        elif mode == "llm-context":
            params = {"q": query, "count": ns.count}
            if ns.freshness:
                params["freshness"] = ns.freshness
            data = _get("llm/context", params, api_key)
            md = _format_llm_context(data, query)
        elif mode == "answers":
            payload = {
                "messages": [{"role": "user", "content": query}],
                "model": "brave",
                "stream": False,
            }
            data = _post("chat/completions", payload, api_key)
            md = _format_answers(data, query)
        else:
            raise SystemExit(f"Unknown mode {mode!r}")

        slug = query.lower().replace(" ", "_")[:50]
        default_out = Path(f"research/brave_{mode}_{slug}.md")
        dest = raw_destination(vault, ns.out or default_out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md, encoding="utf-8")
        return IngestResult(dest, f"Wrote {dest.relative_to(vault)}")
