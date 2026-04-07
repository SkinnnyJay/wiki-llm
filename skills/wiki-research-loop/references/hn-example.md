# Hacker News (example)

Used by **wiki-research-loop** batch tasks. For a **one-off research topic** (not `research-tasks.json`), use **wiki-research** / **`/llm-wiki:research`** instead.

- Use the **Firebase API**: `https://hacker-news.firebaseio.com/v0/topstories.json` and `/item/<id>.json`.
- Prefer **`llm-wiki ingest hackernews`** over HTML scraping of news.ycombinator.com.
- Respect reasonable **rate limits**; use `research_loop.delay_seconds_between_fetches` when batching many items. Raise limits only if you add delays — avoid hammering the public API.
- Comments: item JSON `kids` lists comment IDs. CLI: `llm-wiki ingest hackernews --depth comments --comment-limit 12` (fetches top-level comments per story).

## Other URLs (`fetch_urls` / `url` adapter)

- Check **robots.txt** and the site’s **terms of use** before automated fetches.
- Do not bypass paywalls, logins, or rate limits. No credential stuffing.

## “Scheduled” runs (plugin has no built-in cron)

Claude Code does not ship a scheduler. For recurring passes:

1. **Manual / slash:** `/llm-wiki:research-loop` or `llm-wiki research-loop`.
2. **External cron / Launchd / CI:** invoke the CLI on a timer, e.g. `llm-wiki research-loop` from a checkout that has `research_loop.enabled` and tasks with `run: true`, or run `claude` with a one-line prompt that triggers **wiki-research-loop** / ingest flows.

Keep `max_items_per_run` conservative unless you control backoff.
