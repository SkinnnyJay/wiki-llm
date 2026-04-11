<!-- Full procedure for **wiki-extract-youtube**. Thin skill: `skills/wiki-extract-youtube/SKILL.md`. -->

# Wiki extract — YouTube

Extracts content from YouTube videos into `raw/` for wiki ingestion. Prioritizes **transcript/caption extraction** (no download required) over full video download. Use when:
- The user shares a YouTube URL to research or summarize.
- A lecture, talk, or interview needs to be captured in the vault.
- "Watch this video and summarize it" / "add this talk to the wiki".

---

## Setup (one-time)

```bash
# yt-dlp (preferred — actively maintained, handles age-restricted content)
pip install yt-dlp
# or: brew install yt-dlp

# pytube (lightweight alternative — may lag on YouTube changes)
pip install pytube

# Verify:
yt-dlp --version
```

yt-dlp is strongly preferred over pytube — YouTube's internal API changes frequently and yt-dlp has a larger community keeping it current.

---

## Step 1 — Identify the URL type

| Input | Action |
|-------|--------|
| Single video URL (`youtube.com/watch?v=...` or `youtu.be/...`) | Extract transcript + metadata |
| Playlist URL | Ask user how many videos; default to first 5 |
| Channel URL | Ask user for topic filter or max count |
| YouTube search query | Use `yt-dlp "ytsearch5:<query>"` to find top 5 |

---

## Step 2 — Extract transcript / captions (no download needed)

This is the preferred path — no large file download required.

### yt-dlp transcript extraction

```bash
VIDEO_URL="https://www.youtube.com/watch?v=<ID>"
SLUG="<video-slug>"
OUT_DIR="raw/videos/${SLUG}"
mkdir -p "$OUT_DIR"

# Download auto-generated captions (no video download)
yt-dlp \
  --skip-download \
  --write-auto-sub \
  --write-sub \
  --sub-lang en \
  --sub-format vtt \
  --output "${OUT_DIR}/${SLUG}" \
  "$VIDEO_URL"

# Convert VTT to plain text (strips timestamps)
python3 << 'PYEOF'
import re, sys, pathlib

vtt_file = sys.argv[1]
text = pathlib.Path(vtt_file).read_text()
# Remove VTT header and timestamps
text = re.sub(r'WEBVTT\n.*?\n\n', '', text, flags=re.DOTALL)
text = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3} --> .*\n', '', text)
text = re.sub(r'<[^>]+>', '', text)          # strip HTML tags
text = re.sub(r'\n{3,}', '\n\n', text)        # collapse blank lines
# Remove duplicate lines (VTT repeats lines)
lines = text.splitlines()
deduped = [lines[0]] if lines else []
for line in lines[1:]:
    if line.strip() != deduped[-1].strip():
        deduped.append(line)
print('\n'.join(deduped))
PYEOF
# Usage:
python3 -c "..." "${OUT_DIR}/${SLUG}.en.vtt" > "${OUT_DIR}/transcript.txt"
```

### pytube transcript extraction (fallback)

```python
# scripts/.tmp/yt_transcript.py
from pytube import YouTube
import sys

url = sys.argv[1]
yt = YouTube(url)
caption = yt.captions.get_by_language_code('en') or \
          yt.captions.get_by_language_code('a.en')  # auto-generated
if caption:
    print(caption.generate_srt_captions())
else:
    print(f"No English captions found. Available: {list(yt.captions.keys())}")
```

```bash
python3 scripts/.tmp/yt_transcript.py "https://youtu.be/<ID>" > /tmp/transcript.srt
```

---

## Step 3 — Fetch video metadata

```bash
VIDEO_URL="https://www.youtube.com/watch?v=<ID>"

# Get metadata as JSON (no download)
yt-dlp --dump-json --skip-download "$VIDEO_URL" > /tmp/yt-meta.json

# Extract key fields:
python3 << 'PYEOF'
import json, sys
meta = json.load(open('/tmp/yt-meta.json'))
print(f"Title:    {meta['title']}")
print(f"Channel:  {meta['channel']}")
print(f"Date:     {meta['upload_date']}")
print(f"Duration: {meta['duration']}s")
print(f"Views:    {meta['view_count']}")
print(f"URL:      {meta['webpage_url']}")
print(f"Chapters: {meta.get('chapters', [])}")
PYEOF
```

---

## Step 4 — Write to raw/ with frontmatter

Output path: `raw/videos/<channel-slug>/<video-slug>.md`

```bash
VIDEO_URL="https://www.youtube.com/watch?v=<ID>"
SLUG="<video-slug>"

cat > "raw/videos/${SLUG}.md" << EOF
---
title: "<Video Title>"
channel: "<Channel Name>"
source_url: ${VIDEO_URL}
source_type: video
platform: youtube
upload_date: YYYY-MM-DD
duration_seconds: <N>
view_count: <N>
fetched_date: $(date +%Y-%m-%d)
has_transcript: true | false
transcript_source: auto_captions | manual_captions | none
---

# <Video Title>

**Channel:** <Channel>  
**Published:** YYYY-MM-DD  
**Duration:** Xh Ym  

## Summary
<3–5 sentence summary of the video content>

## Transcript

EOF
cat /tmp/transcript-cleaned.txt >> "raw/videos/${SLUG}.md"
```

---

## Step 5 — When no captions exist: audio transcription

If `yt-dlp` reports no captions available:

```bash
# Option A: Download audio and transcribe with Whisper
yt-dlp --extract-audio --audio-format mp3 \
  --output "/tmp/%(title)s.%(ext)s" "$VIDEO_URL"

# Transcribe with Whisper (requires: pip install openai-whisper)
whisper /tmp/<title>.mp3 --model base --language en --output_format txt \
  --output_dir raw/videos/<slug>/

# Option B: Use llm-wiki integrations if a speech-to-text adapter is configured
llm-wiki integrations status | grep -i whisper
```

Audio download + Whisper transcription is slower and larger — ask the user before doing this for videos longer than 30 minutes.

---

## Step 6 — Playlist handling

```bash
PLAYLIST_URL="https://www.youtube.com/playlist?list=<ID>"

# List all videos in playlist (no download)
yt-dlp --flat-playlist --dump-json "$PLAYLIST_URL" | \
  python3 -c "
import json, sys
for line in sys.stdin:
    v = json.loads(line)
    print(v['id'], v.get('title','?'))
"

# Extract transcripts for first N videos:
yt-dlp --flat-playlist --dump-json "$PLAYLIST_URL" | head -5 | \
  python3 -c "
import json, sys, subprocess
for line in sys.stdin:
    v = json.loads(line)
    url = f\"https://youtube.com/watch?v={v['id']}\"
    subprocess.run(['yt-dlp', '--skip-download', '--write-auto-sub',
                    '--sub-lang', 'en', '--sub-format', 'vtt', url])
"
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `yt-dlp: ERROR: Sign in to confirm your age` | Add cookies: `yt-dlp --cookies-from-browser chrome <URL>` |
| No English captions available | Use audio transcription (Step 5) or check other languages |
| VTT file is empty | Video has no auto-captions; check if manual captions exist with `--list-subs` |
| pytube `KeyError` or `RegexMatchError` | YouTube changed their internal API; switch to yt-dlp |
| `yt-dlp: HTTP Error 403` | Outdated yt-dlp; run `pip install -U yt-dlp` |
| Whisper out of memory | Use `--model tiny` instead of base; or `--model small` |
| Transcript is gibberish (music/no speech) | Video is music/silent; note `transcript_source: none` |

---

## Done looks like

- At least one **`raw/`** markdown file with **`source_url`**, title/channel metadata, and transcript body (or explicit **no captions** + agreed fallback path).
- Large downloads (audio/Whisper) only with user consent for long videos.

## Related skills

- **wiki-research** — orchestrator that invokes this for YouTube URLs
- **wiki-research-social** — for YouTube comments or Twitter discussions about a video
- **wiki-extract-ebook** — for offline text extraction (non-video)
- **wiki-raw-prepare** — clean transcript markdown before wiki ingestion

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

