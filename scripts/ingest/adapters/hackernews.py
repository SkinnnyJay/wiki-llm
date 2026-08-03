from __future__ import annotations

import json
import re
import sys
import time
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, ClassVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lib.http_defaults import USER_AGENT
from lib.paths import raw_destination

from ingest.base import Adapter, IngestResult

HN_API = "https://hacker-news.firebaseio.com/v0"
_ITEM_URL = re.compile(r"https?://news\.ycombinator\.com/item\?id=(\d+)", re.IGNORECASE)
# Firebase can throttle bursty clients; small pause between requests in comments mode.
_HN_REQUEST_GAP_S = 0.12
_REQUEST_TIMEOUT_S = 20


def _parse_item_ref(raw: str) -> int | None:
    """HN numeric id or item URL → id; else None."""
    s = raw.strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    m = _ITEM_URL.search(s)
    if m:
        return int(m.group(1))
    # Loose: ?id=NNN anywhere
    m2 = re.search(r"[?&]id=(\d+)", s)
    if m2:
        return int(m2.group(1))
    return None


def _get_json(url: str) -> Any:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=_REQUEST_TIMEOUT_S) as r:
            return json.loads(r.read().decode())
    except HTTPError as e:
        print(f"hackernews: HTTP {e.code} for {url}", file=sys.stderr)
        raise SystemExit(2) from e
    except URLError as e:
        print(f"hackernews: network error for {url}: {e.reason!r}", file=sys.stderr)
        raise SystemExit(2) from e


class HackerNewsAdapter(Adapter):
    id: ClassVar[str] = "hackernews"
    label: ClassVar[str] = "Fetch HN top stories or one item (id/URL) via Firebase API"
    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "integration_keys": [],
        "notes": (
            "Uses https://hacker-news.firebaseio.com/v0/ (no API key). "
            "topstories.json is the top ~500 story ids by rank — not identical to the visible "
            "front page order on news.ycombinator.com. "
            "--depth comments issues many sequential HTTP requests; expect tens of seconds."
        ),
    }

    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        p = ArgumentParser(prog="llm-wiki ingest hackernews")
        p.add_argument(
            "item",
            nargs="?",
            default=None,
            help="Optional HN item id or item page URL (fetch this item only; omit for top stories)",
        )
        p.add_argument("--limit", type=int, default=10)
        p.add_argument(
            "--depth",
            choices=("stories", "comments"),
            default="stories",
            help="stories: titles only; comments: one HTTP request per top-level comment (slow; progress on stderr)",
        )
        p.add_argument(
            "--comment-limit",
            type=int,
            default=12,
            help="Max top-level comments to fetch per story (depth=comments)",
        )
        p.add_argument("--out", type=Path, default=Path("research/hn-top.md"))
        ns = p.parse_args(argv)
        single: int | None = None
        if ns.item is not None:
            single = _parse_item_ref(ns.item)
            if single is None:
                print(
                    f"hackernews: could not parse item id or URL: {ns.item!r} "
                    f"(use a number or e.g. https://news.ycombinator.com/item?id=NNN)",
                    file=sys.stderr,
                )
                raise SystemExit(2)
            ids = [single]
            lines = [
                "# Hacker News item\n",
                f"**id:** {single}\n",
                f"Depth: {ns.depth}\n\n---\n\n",
            ]
        else:
            ids = _get_json(f"{HN_API}/topstories.json")[: ns.limit]
            lines = [
                "# Hacker News top stories\n",
                f"Count: {len(ids)} (from topstories.json — see adapter notes; may differ from website order)\n",
                f"Depth: {ns.depth}\n\n---\n\n",
            ]
        total = len(ids)
        for idx, i in enumerate(ids):
            print(
                f"hackernews: story {idx + 1}/{total} (id={i}) …",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(_HN_REQUEST_GAP_S)
            item = _get_json(f"{HN_API}/item/{i}.json")
            if not item:
                continue
            title = item.get("title") or "(no title)"
            url = item.get("url") or f"https://news.ycombinator.com/item?id={i}"
            lines.append(f"## {title}\n\n- **id:** {i}\n- **url:** {url}\n- **score:** {item.get('score')}\n\n")
            if item.get("text"):
                body = (item.get("text") or "").replace("<p>", "\n").replace("</p>", "\n")
                lines.append(f"{body}\n\n")
            if ns.depth == "comments" and item.get("kids"):
                kids = item["kids"][: ns.comment_limit]
                lines.append("### Top comments\n\n")
                print(
                    f"  hackernews: fetching {len(kids)} top-level comments for story id={i} …",
                    file=sys.stderr,
                    flush=True,
                )
                for cix, kid in enumerate(kids):
                    if cix and cix % 5 == 0:
                        print(
                            f"  hackernews: comments {cix}/{len(kids)} (story id={i}) …",
                            file=sys.stderr,
                            flush=True,
                        )
                    time.sleep(_HN_REQUEST_GAP_S)
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
