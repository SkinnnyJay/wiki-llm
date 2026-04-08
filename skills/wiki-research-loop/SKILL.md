---
name: wiki-research-loop
description: Batch research from research-tasks.json — fetch, ingest, wiki merge. Use when research_loop.enabled for automated passes (e.g. HN front page).
disable-model-invocation: true
context: fork
agent: research-runner
effort: high
---

# Research loop (batch tasks)

**Not** ad-hoc topic research — for a user **topic or question**, use **wiki-research** and **`/llm-wiki:research`**.

**Requires `research_loop.enabled: true`** in `llm-wiki/config.json`. If false, tell the user to enable it.

1. Load **`llm-wiki/research-tasks.json`** or **`research-tasks.yaml`** (or the path in **`research_loop.tasks_file`**; YAML needs `pip install pyyaml`).
2. For each task with `run: true` (or user-specified id), respect **`max_items_per_run`** and **`delay_seconds_between_fetches`**.
3. Optional batching: **`llm-wiki research-loop`** runs `hackernews_top` and `fetch_urls` tasks from the JSON/YAML file; then apply **wiki-ingest** / **wiki-maintainer** for anything written to **`raw/`**.
4. Or use **`llm-wiki ingest`** (e.g. `hackernews`, `url`) directly to write into **`raw/`**; then apply **wiki-ingest** / **wiki-maintainer**.
5. See **`references/hn-example.md`** for Hacker News API usage and ethics (rate limits, ToS).

Do not scrape aggressively; prefer official APIs.

Optional: `skills/references/context-persona.md` for ingest/tool alignment; `persona.name` in config (default **Gennie**).

## Done looks like

- **`research_loop.enabled: true`** confirmed (or user told how to enable it).
- Tasks loaded; delays and **`max_items_per_run`** respected; new files under **`raw/`**; **wiki-ingest** / **wiki-maintainer** applied for batch merge when requested.
- **`wiki/log.md`** updated for the loop run when non-trivial.

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

