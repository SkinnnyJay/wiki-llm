---
name: wiki-research
description: Ad-hoc research orchestrator — classifies request, picks sub-skill, ingests, and merges into wiki/. Not wiki-research-loop (batch tasks).
when_to_use: Use for ad-hoc research questions, topics, or URLs that need source selection, acquisition into raw/, and a curated wiki merge; use wiki-research-loop for recurring task files.
argument-hint: "<topic, URL, or question>"
---

# Wiki research (orchestrator)

**Naming:** This skill is **wiki-research** (ad-hoc **topic**). Use **wiki-research-loop** only for recurring **batch** runs from `research_loop.tasks_file`.

## When to use

- User gives a **research question, topic, or URL** (not a predeclared JSON task list).
- You need to discover the right fetch strategy, pull content into `raw/`, then merge into `wiki/`.

---

## Pre-flight check

Before classifying the request, verify the vault is ready. If **`llm-wiki/.agent-memory.md`** exists, skim **Pitfalls** and **Preferences** (**wiki-learn**) before heavy research. If **`memory.enabled`**, optionally **`llm-wiki memory recall "<topic>"`** to see whether past sessions covered this topic (**wiki-session-memory**).

```bash
python3 -c "
import json, pathlib, sys
p = pathlib.Path('llm-wiki/config.json')
if not p.exists():
    print('PRE_FLIGHT: FAIL — config.json not found')
    sys.exit(1)
meta = json.loads(p.read_text()).get('_meta', {})
if not meta.get('setup_completed'):
    print('PRE_FLIGHT: WARN — setup not completed')
else:
    print('PRE_FLIGHT: OK')
"
```

**On `FAIL`:** Stop. Offer to run **wiki-setup** now:
> The llm-wiki vault is not initialized. Would you like me to run the setup wizard?
> - `[1]` Yes — run wiki-setup
> - `[2]` No — cancel

**On `WARN`:** Inform the user and ask:
> The vault exists but setup hasn't been completed. Some integrations may not work.
> - `[1]` Continue anyway
> - `[2]` Run wiki-setup first

**On `OK`:** Proceed directly to Step 1.

See `skills/references/preflight.md` for the full pre-flight pattern and integration-specific checks.

---

## Step 1 — Classify the request

Read `$ARGUMENTS` (or the user's message) and assign a **primary modality**:

| Signal | Modality | Sub-skill to invoke |
|--------|----------|---------------------|
| A URL (http/https) | web page | **wiki-research-web** |
| arXiv ID, DOI, "paper", "study", "preprint" | academic | **wiki-research-academic** |
| Twitter/X link, HN link, "thread", "tweet", Reddit URL | social | **wiki-research-social** |
| "feed", "RSS", OPML, newsletter URL | feeds | **wiki-research-feeds** |
| "news", "latest", "current events", "what happened" | news | **wiki-research-news** |
| Broad topic needing multiple passes / "deep research" | deep | **wiki-research-deep** |
| YouTube URL (`youtube.com`, `youtu.be`) | video | **wiki-extract-youtube** |
| "paywall", "can't access", 403 response, "bypass" | paywall | **wiki-extract-paywall** |
| `.epub`, `.pdf`, `.mobi`, `.azw3`, local file path | ebook | **wiki-extract-ebook** |
| "find the book", "download this paper", "Anna's Archive" | book search | **wiki-extract-annas** |

When ambiguous, default to **wiki-research-web** for URLs and **wiki-research-deep** for open-ended topics.

Open `skills/wiki-research/references/approaches.md` to see the full dispatch table with example triggers.

---

## Step 2 — Dispatch to sub-skill

Invoke the matched sub-skill and follow its instructions exactly. Pass the original `$ARGUMENTS` and any relevant context (vault paths, config) forward.

Sub-skill reference files:
- `skills/wiki-research/references/approaches.md` — full dispatch table and decision tree
- `skills/wiki-research/references/query-design.md` — how to construct queries per modality
- `skills/wiki-research/references/source-eval.md` — scoring, dedup, prompt-injection checks
- `skills/wiki-research/references/synthesis.md` — merging multi-source findings into wiki pages

---

## Step 3 — Post-process (always runs)

Regardless of which sub-skill ran:

1. **Validate raw files** — `llm-wiki raw validate` on any new files in `raw/`
2. **Merge into wiki** — invoke **wiki-ingest** and **wiki-maintainer**
3. **Log** — append `wiki/log.md`:
   ```
   ## [YYYY-MM-DD] research | <short topic>
   - Modality: <web|academic|social|feeds|news|deep>
   - Sources: <paths under raw/>
   - Pages touched: <wiki/ paths>
   - Open questions: …
   ```
4. **Optional git snapshot** — `llm-wiki git snapshot -m "research: <topic> [ingest]" --phase ingest` then `--phase wiki` after merge (if `git.enabled`)

---

## Done looks like

- Pre-flight **OK** (or user explicitly continued after **WARN**).
- Sub-skill completed; **`llm-wiki raw validate`** run on new **`raw/`** files; **wiki-ingest** and **wiki-maintainer** applied; **`wiki/log.md`** has a dated **`research | …`** entry with modality, sources, pages touched, and open questions.
- Optional: vault git snapshots with phase tags when **`git.enabled`**.

## Artifacts

| Layer | Use |
|-------|-----|
| `raw/` | Evidence: fetched text, URLs in body or frontmatter. Do not alter provenance. |
| `wiki/` | Curated synthesis with `[[wikilinks]]` and `raw/` citations. |
| `outputs/` | Scratch drafts for deep research; promote to `wiki/` only after review. |

---

## Related skills

- **wiki-research-web** — URL / web page fetching
- **wiki-research-academic** — arXiv, DOI, Semantic Scholar
- **wiki-research-social** — Twitter/X, Hacker News, Reddit
- **wiki-research-feeds** — RSS / Atom / newsletters
- **wiki-research-news** — current events via Perplexity or news APIs
- **wiki-research-deep** — multi-pass, multi-source synthesis
- **wiki-research-loop** — batch tasks from `research-tasks.json`
- **wiki-extract-youtube** — YouTube transcripts and captions
- **wiki-extract-paywall** — bypass paywalled articles (Freedium, archive.ph, 12ft.io, etc.)
- **wiki-extract-ebook** — extract text from EPUB, PDF, MOBI, AZW3
- **wiki-extract-annas** — search and download from Anna's Archive
- **wiki-ingest** — merge `raw/` into `wiki/`
- **wiki-maintainer** — index, cross-links, consistency
- **wiki-raw-prepare** — clean structurally broken markdown in `raw/`
- **wiki-session-memory** — recall past sessions on the topic (`raw/memory/`)
- **wiki-fetch** — single-URL fetch without wiki merge (lightweight)

Optional: `skills/references/context-persona.md` and `persona.name` in `llm-wiki/config.json` (default **Gennie**).

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

