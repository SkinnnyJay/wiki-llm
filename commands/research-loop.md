---
description: Run recurring research tasks from research-tasks.json (or tasks_file in config; when research_loop.enabled).
---

For **ad-hoc topic research** (no task file), use **`/llm-wiki:research`** and the **wiki-research** skill.

1. Confirm `research_loop.enabled` in `llm-wiki/config.json`. If false, explain and stop.
2. Load the research tasks file (`llm-wiki/research-tasks.json` by default, or `research_loop.tasks_file` in config) and follow **wiki-research-loop** skill: for each task with `run: true` (or user-selected), fetch sources via `llm-wiki ingest` **or** the batch CLI below, respect `max_items_per_run` and rate limits, then merge into the wiki.

**CLI (optional):** `llm-wiki research-loop` — flags `--dry-run`, `--task <id>`, `--force`. Tasks use `source: hackernews_top` or `fetch_urls` (see template `research-tasks.json`). YAML task files need `pip install pyyaml`.

$ARGUMENTS
