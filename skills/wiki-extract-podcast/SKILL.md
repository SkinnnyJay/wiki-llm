---
name: wiki-extract-podcast
description: Extract podcast episodes from RSS and transcribe via Whisper or AssemblyAI into raw/. Use for podcast URLs or episode links.
disable-model-invocation: true
argument-hint: "<podcast URL or RSS feed>"
---

# Wiki extract — podcast

Extracts podcast episodes from RSS feeds and transcribes audio into `raw/` for wiki ingestion. Use when:
- The user shares a podcast episode URL or RSS feed link.
- A podcast series needs to be tracked in the vault.
- "Transcribe this episode", "add this podcast to the wiki", "summarize episode X of Y".

Mirrors **wiki-extract-youtube** but for audio-only sources with RSS-based discovery.

---

## Step 1 — Identify the input type

| Input | Action |
|-------|--------|
| Direct MP3/M4A URL | Download and transcribe (Step 4) |
| Podcast episode page URL (e.g. Spotify, Apple Podcasts, Overcast) | Extract RSS feed → find episode (Step 2) |
| RSS feed URL | Parse feed, select episodes (Step 3) |
| Podcast name / search query | Find RSS feed via Podcast Index API (Step 2) |

---

## Step 2 — Find the RSS feed

### From a podcast name or directory URL

```bash
# Podcast Index API (free, requires key from https://podcastindex.org/developer)
PODCAST_INDEX_KEY="${PODCAST_INDEX_KEY:-}"
PODCAST_INDEX_SECRET="${PODCAST_INDEX_SECRET:-}"

python3 << 'PYEOF'
import hashlib, time, urllib.request, urllib.parse, json, os, sys

API_KEY    = os.environ['PODCAST_INDEX_KEY']
API_SECRET = os.environ['PODCAST_INDEX_SECRET']
query      = sys.argv[1]

ts   = str(int(time.time()))
auth = hashlib.sha1(f"{API_KEY}{API_SECRET}{ts}".encode()).hexdigest()

params = urllib.parse.urlencode({'q': query, 'max': 5})
url    = f"https://api.podcastindex.org/api/1.0/search/byterm?{params}"
req    = urllib.request.Request(url, headers={
    'X-Auth-Key': API_KEY,
    'X-Auth-Date': ts,
    'Authorization': auth,
    'User-Agent': 'wiki-llm-research/1.0'
})
with urllib.request.urlopen(req) as r:
    data = json.loads(r.read())

for f in data.get('feeds', []):
    print(f"{f['id']:8} {f['title'][:50]:<50} {f['url']}")
PYEOF
python3 -c "..." "Lex Fridman Podcast"
```

### From an episode page URL (Apple Podcasts, Overcast, etc.)

```bash
# Fetch the page and look for <link type="application/rss+xml"> or feed URLs
llm-wiki ingest url "<episode-page-url>" --out /tmp/ep-page.md
# Look for RSS URL patterns in the output
```

---

## Step 3 — Parse the RSS feed

```bash
RSS_URL="<feed-url>"
SLUG="<podcast-slug>"
OUT_DIR="raw/podcasts/${SLUG}"
mkdir -p "$OUT_DIR"

python3 << 'PYEOF'
import urllib.request, xml.etree.ElementTree as ET, json, sys

rss_url = sys.argv[1]
req = urllib.request.Request(rss_url, headers={'User-Agent': 'wiki-llm-research/1.0'})
with urllib.request.urlopen(req) as r:
    tree = ET.parse(r)

root    = tree.getroot()
channel = root.find('channel')
ns      = {'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd'}

episodes = []
for item in channel.findall('item'):
    enc = item.find('enclosure')
    episodes.append({
        'title':    item.findtext('title', ''),
        'pub_date': item.findtext('pubDate', ''),
        'duration': item.findtext('itunes:duration', '', ns),
        'summary':  item.findtext('itunes:summary', '') or item.findtext('description', ''),
        'audio_url': enc.get('url') if enc is not None else '',
        'guid':     item.findtext('guid', ''),
    })

# Print feed info + first 10 episodes
print(json.dumps({
    'title':       channel.findtext('title', ''),
    'description': channel.findtext('description', ''),
    'link':        channel.findtext('link', ''),
    'episodes':    episodes[:10]
}, indent=2))
PYEOF
python3 -c "..." "$RSS_URL" > "${OUT_DIR}/feed.json"
```

Ask the user which episodes to transcribe (default: latest 1). Show title + date list.

---

## Step 4 — Download audio

```bash
AUDIO_URL="<from feed.json enclosure url>"
SLUG="<episode-slug>"
OUT_DIR="raw/podcasts/<podcast-slug>"

# Prefer yt-dlp for broad compatibility (handles Spotify embeds, SoundCloud, etc.)
yt-dlp --extract-audio --audio-format mp3 \
  --output "${OUT_DIR}/${SLUG}.%(ext)s" \
  "$AUDIO_URL"

# Or direct download for plain MP3 URLs
curl -L "$AUDIO_URL" -o "${OUT_DIR}/${SLUG}.mp3"
```

For episodes longer than 60 minutes, warn the user that Whisper transcription will take several minutes.

---

## Step 5 — Transcribe audio

### Option A — Whisper (local, free)

```bash
# Install: pip install openai-whisper
# Models: tiny (fast), base (default), small, medium, large (most accurate)

whisper "${OUT_DIR}/${SLUG}.mp3" \
  --model base \
  --language en \
  --output_format txt \
  --output_dir "${OUT_DIR}/"
# Output: ${OUT_DIR}/${SLUG}.txt
```

Model selection guide:
| Model | Speed | Accuracy | Use when |
|-------|-------|----------|----------|
| `tiny` | Very fast | Low | Quick draft, long episodes |
| `base` | Fast | Good | Default for most episodes |
| `small` | Moderate | Better | Technical vocabulary |
| `medium` | Slow | High | Final, high-quality transcription |
| `large` | Very slow | Best | Max accuracy, short clips |

### Option B — AssemblyAI (API, faster than local Whisper)

```bash
# Requires: pip install assemblyai
# Requires: ASSEMBLYAI_API_KEY env var

python3 << 'PYEOF'
import assemblyai as aai, os, sys

aai.settings.api_key = os.environ['ASSEMBLYAI_API_KEY']
config = aai.TranscriptionConfig(speaker_labels=True, auto_chapters=True)
transcriber = aai.Transcriber(config=config)

transcript = transcriber.transcribe(sys.argv[1])  # file path or URL

# Speaker-labeled output
for utt in transcript.utterances:
    print(f"[{utt.speaker}] {utt.text}\n")
PYEOF
python3 -c "..." "${OUT_DIR}/${SLUG}.mp3" > "${OUT_DIR}/transcript.txt"
```

AssemblyAI is preferred when `ASSEMBLYAI_API_KEY` is available: it's faster than local Whisper, supports speaker diarization, and returns chapter markers automatically.

---

## Step 6 — Write to raw/ with frontmatter

Output path: `raw/podcasts/<podcast-slug>/<YYYY-MM-DD>-<episode-slug>.md`

```bash
cat > "${OUT_DIR}/<YYYY-MM-DD>-${SLUG}.md" << EOF
---
title: "<Episode Title>"
podcast: "<Podcast Name>"
episode_number: <N>
source_url: <episode page URL or audio URL>
source_type: podcast
platform: <rss | spotify | apple | soundcloud>
pub_date: YYYY-MM-DD
duration_seconds: <N>
transcription_model: whisper-base | assemblyai
fetched_date: $(date +%Y-%m-%d)
has_transcript: true
---

# <Episode Title>

**Podcast:** <Podcast Name>
**Episode:** <N> | **Published:** YYYY-MM-DD | **Duration:** Xh Ym

## Summary

<3–5 sentence summary of the episode content>

## Transcript

EOF
cat "${OUT_DIR}/${SLUG}.txt" >> "${OUT_DIR}/<YYYY-MM-DD>-${SLUG}.md"
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `whisper: command not found` | `pip install openai-whisper` (also installs `ffmpeg` dependency) |
| `ffmpeg: command not found` | `brew install ffmpeg` (required by Whisper) |
| Whisper runs out of memory | Use `--model tiny` or `--model base` |
| Audio URL returns 403 | Some hosts expire URLs; re-fetch the RSS feed for a fresh URL |
| yt-dlp can't download Spotify | Spotify embeds require cookies; use `--cookies-from-browser chrome` |
| Transcript is low quality | Episode has music/crosstalk; try `--model small` or `--model medium` |
| `PODCAST_INDEX_KEY` not set | Register free at https://podcastindex.org/developer |
| `ASSEMBLYAI_API_KEY` not set | Register at https://assemblyai.com (free tier available) |
| RSS feed is behind auth | Podcast is private/Patreon-only; you need the subscriber RSS URL |

---

## Done looks like

- Episode audio/transcript path documented; **`raw/`** markdown includes show/episode metadata and transcript or explicit failure reason.

## Related skills

- **wiki-extract-youtube** — for video content; use when the podcast also has a YouTube channel
- **wiki-research-feeds** — for following podcast RSS as a news/update feed (headlines only, no transcription)
- **wiki-research-social** — for Twitter/HN discussion about a specific episode
- **wiki-raw-prepare** — clean and restructure transcripts before wiki ingestion

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

