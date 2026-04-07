---
name: wiki-research-loop
description: Runs recurring research tasks from llm-wiki/research-tasks.json or research-tasks.yaml (research_loop.tasks_file) — fetch, ingest, wiki merge. Use when research_loop.enabled and user wants automated research passes (e.g. HN front page).
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
