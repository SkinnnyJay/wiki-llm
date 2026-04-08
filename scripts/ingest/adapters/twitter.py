from __future__ import annotations

import json
import re
import shutil
import subprocess
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, ClassVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lib.paths import raw_destination
from ingest.base import Adapter, IngestResult

# Public proxy API — no auth, works for any public tweet.
_FXTW_API = "https://api.fxtwitter.com"

# Regex to extract screen name + tweet ID from twitter.com / x.com URLs.
_TWEET_URL_RE = re.compile(
    r"(?:twitter\.com|x\.com)/(@?\w+)/status/(\d+)", re.IGNORECASE
)
# Regex for bare tweet ID (numeric only).
_TWEET_ID_RE = re.compile(r"^\d+$")


def _fxtwitter_fetch(screen_name: str, tweet_id: str) -> dict:
    """Fetch a single tweet via the FxTwitter public proxy (no auth required)."""
    url = f"{_FXTW_API}/{screen_name}/status/{tweet_id}"
    req = Request(url, headers={"User-Agent": "llm-wiki/0.1"})
    try:
        with urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
    except (HTTPError, URLError) as e:
        raise SystemExit(f"FxTwitter API error for {screen_name}/{tweet_id}: {e}") from e
    if data.get("code") != 200 or not data.get("tweet"):
        raise SystemExit(
            f"FxTwitter returned {data.get('code')}: {data.get('message')}. "
            "The tweet may be private, deleted, or the URL is wrong."
        )
    return data


def _parse_tweet_url(url_or_id: str) -> tuple[str, str]:
    """Return (screen_name, tweet_id) from a twitter.com/x.com URL or bare ID."""
    m = _TWEET_URL_RE.search(url_or_id)
    if m:
        return m.group(1).lstrip("@"), m.group(2)
    if _TWEET_ID_RE.match(url_or_id):
        # Bare numeric ID — we don't know the screen name; use a generic path
        # FxTwitter accepts any valid screen_name placeholder for ID-only lookups
        raise SystemExit(
            "Please pass a full twitter.com or x.com URL (not just a tweet ID). "
            "Example: https://x.com/user/status/123456789"
        )
    raise SystemExit(
        f"Cannot parse tweet URL from {url_or_id!r}. "
        "Pass a full https://x.com/<user>/status/<id> URL."
    )


def _format_fxtwitter(data: dict) -> str:
    """Render FxTwitter API response as clean markdown."""
    tweet = data.get("tweet") or {}
    author = tweet.get("author") or {}
    name = author.get("name") or "?"
    handle = author.get("screen_name") or "?"
    text = tweet.get("text") or ""
    created = tweet.get("created_at") or ""
    likes = tweet.get("likes") or 0
    retweets = tweet.get("retweets") or 0
    views = tweet.get("views") or 0
    url = tweet.get("url") or ""

    lines = [
        f"# Tweet by @{handle}\n",
        f"**{name}** (@{handle})",
        f"Posted: {created}  ",
        f"URL: {url}\n",
        "---\n",
        text,
        "\n---\n",
        f"❤️ {likes}  🔁 {retweets}  👁 {views}",
    ]

    # Quoted tweet
    quoted = tweet.get("quote")
    if quoted:
        q_handle = (quoted.get("author") or {}).get("screen_name") or "?"
        q_text = quoted.get("text") or ""
        lines += [f"\n\n> **Quoting @{q_handle}:**\n> {q_text}"]

    # Media
    media = tweet.get("media") or {}
    photos = media.get("photos") or []
    videos = media.get("videos") or []
    if photos:
        lines += ["\n\n**Media:**"]
        for p in photos:
            lines.append(f"- ![photo]({p.get('url', '')})")
    if videos:
        for v in videos:
            lines.append(f"- 🎥 {v.get('url', '')}")

    return "\n".join(lines) + "\n"


def _run_bird(argv: list[str]) -> str:
    """Run the bird CLI and return its stdout."""
    result = subprocess.run(
        ["bird", *argv],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise SystemExit(f"bird CLI failed (rc={result.returncode}): {result.stderr.strip()}")
    return result.stdout.strip()


def _bird_tweet_to_md(raw: str, source_url: str) -> str:
    """Convert bird JSON or plain-text output to markdown."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return f"# Twitter / X\n\nSource: {source_url}\n\n{raw}\n"

    if isinstance(data, list):
        # Search or timeline result — list of tweet objects
        lines = [f"# Twitter results\n\nQuery: {source_url}\n\n---\n"]
        for item in data:
            handle = (item.get("author") or item.get("user") or {}).get("screen_name") or "?"
            text = item.get("text") or item.get("full_text") or ""
            url = item.get("url") or ""
            lines.append(f"## @{handle}\n\n{text}\n\n_{url}_\n")
        return "\n".join(lines)

    # Single tweet
    handle = (data.get("author") or data.get("user") or {}).get("screen_name") or "?"
    text = data.get("text") or data.get("full_text") or ""
    url = data.get("url") or source_url
    return f"# Tweet by @{handle}\n\nURL: {url}\n\n---\n\n{text}\n"


class TwitterAdapter(Adapter):
    """
    Fetch tweets, threads, or search results into raw/.

    Priority:
      1. bird CLI  (npm install -g @steipete/bird + TWITTER_AUTH_TOKEN) — threads, search, timeline
      2. FxTwitter public API — zero config, public tweet URLs only

    Install bird:  npm install -g @steipete/bird
    Auth:          export TWITTER_AUTH_TOKEN=<your_browser_auth_token>
    Get token:     Twitter → DevTools → Application → Cookies → auth_token
    """

    id: ClassVar[str] = "twitter"
    label: ClassVar[str] = (
        "Fetch tweet/thread (bird CLI preferred, FxTwitter API fallback — "
        "zero config for public tweets)"
    )
    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "api_key_env": "TWITTER_AUTH_TOKEN",
        "prefer_cli": True,
        "_notes": (
            "Install bird: npm install -g @steipete/bird  "
            "Auth: export TWITTER_AUTH_TOKEN=<token>  "
            "FxTwitter API works zero-config for single public tweets."
        ),
    }

    @classmethod
    def setup_checks(cls, cfg_slice: dict[str, Any]) -> list[str]:
        import os

        has_cli = bool(shutil.which("bird"))
        has_token = bool(os.environ.get("TWITTER_AUTH_TOKEN"))
        if not has_cli:
            return [
                "Optional: npm install -g @steipete/bird for threads/search/timeline "
                "(FxTwitter API works zero-config for basic public tweets)"
            ]
        if not has_token:
            return ["Set TWITTER_AUTH_TOKEN to enable bird CLI auth (timeline/bookmarks require it)"]
        return []

    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        import os

        slice_ = (cfg.get("integrations") or {}).get("twitter") or {}
        prefer_cli = slice_.get("prefer_cli", True)
        has_cli = bool(shutil.which("bird"))

        p = ArgumentParser(prog="llm-wiki ingest twitter")
        p.add_argument(
            "url_or_query",
            nargs="?",
            help="Tweet URL / ID, or search query (with --search), or @handle (with --user)",
        )
        p.add_argument("--search", metavar="QUERY", help="Search tweets for QUERY")
        p.add_argument("--user", metavar="HANDLE", help="Fetch user timeline (@handle)")
        p.add_argument("--limit", type=int, default=20, help="Max results (search/timeline)")
        p.add_argument("--thread", action="store_true", help="Fetch full thread (bird CLI only)")
        p.add_argument("--out", type=Path)
        ns = p.parse_args(argv)

        # Determine mode
        if ns.search:
            return self._run_search(vault, ns, has_cli and prefer_cli)
        if ns.user:
            return self._run_user(vault, ns, has_cli and prefer_cli)
        if not ns.url_or_query:
            p.error("Provide a tweet URL/ID, --search QUERY, or --user @handle")
        return self._run_tweet(vault, ns, has_cli and prefer_cli, os.environ.get("TWITTER_AUTH_TOKEN", ""))

    def _run_tweet(self, vault: Path, ns: Any, use_cli: bool, token: str) -> IngestResult:
        url = ns.url_or_query
        out_name = re.sub(r"[^a-z0-9_-]", "_", url.lower())[:60]
        dest = raw_destination(vault, ns.out or Path(f"twitter/{out_name}.md"))
        dest.parent.mkdir(parents=True, exist_ok=True)

        if use_cli and ns.thread:
            raw = _run_bird(["thread", url])
            md = _bird_tweet_to_md(raw, url)
        elif use_cli and token:
            raw = _run_bird(["tweet", url])
            md = _bird_tweet_to_md(raw, url)
        else:
            # FxTwitter zero-config fallback
            screen_name, tweet_id = _parse_tweet_url(url)
            data = _fxtwitter_fetch(screen_name, tweet_id)
            md = _format_fxtwitter(data)

        dest.write_text(md, encoding="utf-8")
        return IngestResult(dest, f"Wrote {dest.relative_to(vault)}")

    def _run_search(self, vault: Path, ns: Any, use_cli: bool) -> IngestResult:
        if not use_cli:
            raise SystemExit(
                "Twitter search requires bird CLI. "
                "Install: npm install -g @steipete/bird && export TWITTER_AUTH_TOKEN=<token>"
            )
        query = ns.search
        raw = _run_bird(["search", query, "--limit", str(ns.limit), "--json"])
        md = _bird_tweet_to_md(raw, f'search: "{query}"')
        slug = re.sub(r"[^a-z0-9_-]", "_", query.lower())[:50]
        dest = raw_destination(vault, ns.out or Path(f"twitter/search_{slug}.md"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md, encoding="utf-8")
        return IngestResult(dest, f"Wrote {dest.relative_to(vault)}")

    def _run_user(self, vault: Path, ns: Any, use_cli: bool) -> IngestResult:
        if not use_cli:
            raise SystemExit(
                "Twitter user timeline requires bird CLI. "
                "Install: npm install -g @steipete/bird && export TWITTER_AUTH_TOKEN=<token>"
            )
        handle = ns.user.lstrip("@")
        raw = _run_bird(["user", handle, "--limit", str(ns.limit), "--json"])
        md = _bird_tweet_to_md(raw, f"@{handle} timeline")
        dest = raw_destination(vault, ns.out or Path(f"twitter/{handle}_timeline.md"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md, encoding="utf-8")
        return IngestResult(dest, f"Wrote {dest.relative_to(vault)}")
