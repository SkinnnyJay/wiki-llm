from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import Any, ClassVar

from lib.paths import raw_destination

from ingest.base import Adapter, IngestResult


class YoutubeAdapter(Adapter):
    id: ClassVar[str] = "youtube"
    label: ClassVar[str] = "YouTube transcript (install youtube-transcript-api)"
    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {
        "requires": ["pip package youtube-transcript-api"],
        "notes": "Optional api_key_env if you wrap a paid transcript API later.",
    }

    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError as e:
            raise SystemExit("Install: pip install youtube-transcript-api") from e
        p = ArgumentParser(prog="llm-wiki ingest youtube")
        p.add_argument("video_id_or_url", help="Video ID or youtube.com URL")
        p.add_argument("--out", type=Path)
        ns = p.parse_args(argv)
        vid = ns.video_id_or_url
        if "youtu" in vid:
            from urllib.parse import parse_qs, urlparse

            u = urlparse(vid)
            if u.hostname and "youtu.be" in u.hostname:
                vid = u.path.strip("/")
            else:
                vid = parse_qs(u.query).get("v", [""])[0]
        tr = YouTubeTranscriptApi.get_transcript(vid)
        text = "\n".join(f"{x['text']}" for x in tr)
        md = f"# YouTube transcript\n\nVideo: `{vid}`\n\n---\n\n{text}\n"
        dest = raw_destination(vault, ns.out or Path(f"youtube/{vid}.md"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md, encoding="utf-8")
        return IngestResult(dest, f"Wrote {dest.relative_to(vault)}")
