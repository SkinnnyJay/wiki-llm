# Research Approaches — Dispatch Table

Read this file when you are inside **wiki-research** (the orchestrator) and need to pick the right sub-skill.

---

## Decision Tree

```
Is it one or more URLs?
  └─ Are they youtube.com / youtu.be?           → wiki-extract-youtube
  └─ Are they arXiv / DOI / Semantic Scholar?   → wiki-research-academic
  └─ Are they Twitter/X, HN, or Reddit URLs?    → wiki-research-social
  └─ Are they RSS/Atom feed URLs or OPML?        → wiki-research-feeds
  └─ Fetch returned 403 / paywall / subscription?→ wiki-extract-paywall
  └─ Otherwise (general web pages)               → wiki-research-web

Is it a local file path?
  └─ .epub / .mobi / .azw3 / .pdf / .djvu       → wiki-extract-ebook

Is it a plain question or topic?
  └─ Contains "news", "latest", "today", "current"?   → wiki-research-news
  └─ Contains "paper", "study", "research", "arXiv"?  → wiki-research-academic
  └─ Contains "tweet", "thread", "HN post"?           → wiki-research-social
  └─ Contains "video", "watch", "YouTube", "lecture"? → wiki-extract-youtube
  └─ Contains "book", "ebook", "find this paper", "Anna's Archive"? → wiki-extract-annas
  └─ Contains "paywall", "bypass", "can't access"?    → wiki-extract-paywall
  └─ Narrow enough to answer with 1–3 sources?        → wiki-research-web
  └─ Broad, multi-angle, or "deep research"?          → wiki-research-deep
```

---

## Dispatch Table

| Modality | Trigger phrases / signals | Sub-skill | Typical output path |
|----------|--------------------------|-----------|---------------------|
| **web** | Any http/https URL; "fetch this page"; "read this article" | wiki-research-web | `raw/research/<topic>/<slug>.md` |
| **academic** | arXiv ID (e.g. `2301.12345`); DOI (`10.xxx`); "paper", "preprint", "study", "literature review", `.edu` domain | wiki-research-academic | `raw/academic/<year>/<arxiv-id-or-slug>.md` |
| **social** | `x.com`, `twitter.com`, `news.ycombinator.com`, `reddit.com`; "tweet", "thread", "HN thread", "subreddit" | wiki-research-social | `raw/social/<platform>/<date>/<slug>.md` |
| **feeds** | `.xml` URL, `feed://`, OPML file, "RSS", "Atom", "newsletter", "subscribe" | wiki-research-feeds | `raw/feeds/<source>/<YYYY-MM-DD>.md` |
| **news** | "what's new", "latest", "current events", "today in", "this week", Perplexity query | wiki-research-news | `raw/news/<YYYY-MM-DD>/<topic>.md` |
| **deep** | "deep research", "comprehensive overview", "multi-source", broad open-ended topics, needs synthesis across 3+ sources | wiki-research-deep | `outputs/research-<topic>.md` → promote to `wiki/` |
| **video** | `youtube.com/watch`, `youtu.be`; "YouTube link"; "this lecture"; "watch this talk" | wiki-extract-youtube | `raw/videos/<channel>/<slug>.md` |
| **paywall** | Fetch returned 403 / empty body / "subscribe to read"; "paywall", "bypass"; Medium URL | wiki-extract-paywall | same path as triggering web fetch |
| **ebook** | Local `.epub`, `.pdf`, `.mobi`, `.azw3`, `.djvu` path; "extract this PDF"; "convert this ebook" | wiki-extract-ebook | `raw/books/<title-slug>/` |
| **book search** | "find the book", "download this paper", "Anna's Archive", "can't find this paper"; author + title with no URL | wiki-extract-annas | `raw/books/<title-slug>/` |

---

## Combining Modalities

When a request clearly spans two modalities (e.g. "find the arXiv paper AND the HN discussion about it"), you may run two sub-skills sequentially:

1. Run `wiki-research-academic` for the paper.
2. Run `wiki-research-social` for the HN thread.
3. Let `wiki-research-deep` handle the synthesis if requested, or do it yourself using `skills/wiki-research/references/synthesis.md`.

Do not run more than three sub-skills in a single session without checking in with the user.

---

## Quick-reference: What Each Sub-skill Does

- **wiki-research-web** — Firecrawl CLI/REST or stdlib fallback; one file per URL; minimal processing.
- **wiki-research-academic** — arXiv API search/fetch, DOI resolver, Semantic Scholar; adds academic frontmatter.
- **wiki-research-social** — fxTwitter (zero-config), bird CLI (threads/search), HN API, old.reddit plain-text; dedup by URL/post ID.
- **wiki-research-feeds** — OPML or URL list; `feed` CLI or stdlib XML; recency filter; batch output.
- **wiki-research-news** — Perplexity primary, Brave Search fallback, NewsAPI/Firecrawl last resort; adds `published_date` frontmatter.
- **wiki-research-deep** — runs 2–3 sub-skills in sequence; intermediate draft in `outputs/`; review gate before `wiki/` merge.
- **wiki-extract-youtube** — yt-dlp transcript/caption extraction; falls back to Whisper audio transcription; no video download by default.
- **wiki-extract-paywall** — Freedium (Medium), archive.ph, Wayback Machine, RemovePaywall, 12ft.io, Googlebot spoof; in priority order.
- **wiki-extract-ebook** — ebooklib (EPUB), PyMuPDF/marker (PDF), Calibre (MOBI/AZW3), ddjvu (DJVU); chunks large texts by chapter.
- **wiki-extract-annas** — Anna's Archive search + fast download API; prefers EPUB > PDF > MOBI; passes to wiki-extract-ebook.
