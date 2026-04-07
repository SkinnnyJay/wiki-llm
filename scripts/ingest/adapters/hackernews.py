from __future__ import annotations

import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, ClassVar
from urllib.request import Request, urlopen

from lib.paths import raw_destination
from ingest.base import Adapter, IngestResult

HN_API = "https://hacker-news.firebaseio.com/v0"


def _get_json(url: str) -> Any:
    req = Request(url, headers={"User-Agent": "llm-wiki/0.1"})
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


class HackerNewsAdapter(Adapter):
    id: ClassVar[str] = "hackernews"
    label: ClassVar[str] = "Fetch HN top stories via official Firebase API"
    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "integration_keys": [],
        "notes": "Uses https://hacker-news.firebaseio.com/v0/ (no API key). Prefer over HTML scraping.",
    }

    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        p = ArgumentParser(prog="llm-wiki ingest hackernews")
        p.add_argument("--limit", type=int, default=10)
        p.add_argument(
            "--depth",
            choices=("stories", "comments"),
            default="stories",
            help="stories: titles only; comments: include top-level comment text (rate-limit friendly)",
        )
        p.add_argument(
            "--comment-limit",
            type=int,
            default=12,
            help="Max top-level comments to fetch per story (depth=comments)",
        )
        p.add_argument("--out", type=Path, default=Path("research/hn-top.md"))
        ns = p.parse_args(argv)
        ids = _get_json(f"{HN_API}/topstories.json")[: ns.limit]
        lines = ["# Hacker News top stories\n", f"Count: {len(ids)}\n", f"Depth: {ns.depth}\n\n---\n\n"]
        for i in ids:
            item = _get_json(f"{HN_API}/item/{i}.json")
            if not item:
                continue
            title = item.get("title") or "(no title)"
            url = item.get("url") or f"https://news.ycombinator.com/item?id={i}"
            lines.append(f"## {title}\n\n- **id:** {i}\n- **url:** {url}\n- **score:** {item.get('score')}\n\n")
            if ns.depth == "comments" and item.get("kids"):
                lines.append("### Top comments\n\n")
                for kid in item["kids"][: ns.comment_limit]:
                    c = _get_json(f"{HN_API}/item/{kid}.json")
                    if not c or c.get("deleted"):
                        continue
                    text = (c.get("text") or "").replace("<p>", "\n").replace("</p>", "\n")
                    who = c.get("by") or "?"
                    lines.append(f"- **{who}:** {text}\n\n")
        dest = raw_destination(vault, ns.out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("\n".join(lines), encoding="utf-8")
        return IngestResult(dest, f"Wrote {dest.relative_to(vault)}")
