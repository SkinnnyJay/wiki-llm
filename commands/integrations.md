---
description: Configure optional ingest integrations — Firecrawl, Brave Search, Perplexity, Twitter, PDF adapters, Anna's Archive, and more. Shows status, walks through setup, validates keys.
---

# Integrations wizard

Follow **wiki-setup** for a full conversational wizard. For fetch adapter **priority** when ingesting URLs, see **wiki-fetch**. This command lists CLI flows for keys and validation.

## Quick usage

```bash
llm-wiki integrations status
```

This shows each adapter with `checks=ok` (ready) or `checks=Set <VAR>` (missing key).

## Full guided wizard

Invoke the **wiki-setup** skill to walk through all integrations conversationally — including explanations, sign-up URLs, and persistence instructions. Setup wizard covers:

| Integration | What it enables | Sign-up |
|------------|----------------|---------|
| **Firecrawl** | Best web fetching — cleanest markdown, JS-rendered pages | https://firecrawl.dev/app/api-keys |
| **Brave Search** | Web + news search with LLM-ready output, free tier | https://api.search.brave.com |
| **Perplexity** | AI research queries with source citations | https://www.perplexity.ai/settings/api |
| **Twitter/X** | Full thread fetch and search (public tweets need no key) | Browser DevTools → Cookies → `auth_token` |
| **Anthropic** | Claude Vision PDF extraction (~$0.02/page, best quality) | https://console.anthropic.com/settings/keys |
| **Anna's Archive** | Download ebooks and papers for research | https://annas-archive.org/account |
| **NewsAPI** | Current events headlines | https://newsapi.org/register |

## Manual configuration

To enable/disable an integration in `llm-wiki/config.json`:

```json
"integrations": {
  "firecrawl": {
    "enabled": true,
    "api_key_env": "FIRECRAWL_API_KEY"
  }
}
```

To set a key for the current session:
```bash
export FIRECRAWL_API_KEY="fc-..."
```

To persist across sessions (add to `~/.zshrc`):
```bash
echo 'export FIRECRAWL_API_KEY="fc-..."' >> ~/.zshrc && source ~/.zshrc
```

For Claude Code: add to `~/.claude/settings.json` under the `"env"` key.

## Validate all integrations

```bash
llm-wiki integrations validate
```

Runs a live check for every enabled adapter — verifies keys, dependencies, and reachability.

## Add a new integration manually

```bash
llm-wiki integrations wizard
```

Interactive terminal wizard for adding individual integrations without re-running full setup.

## Arguments

$ARGUMENTS (e.g. which integration to focus in the wizard: `firecrawl`, `perplexity`, …)

## Smoke check

- **CLI:** Run the primary `llm-wiki` command(s) shown in this file; use a configured vault (`LLM_WIKI_VAULT` or `./llm-wiki`).
- **Prompt:** In Claude Code with this plugin loaded, run the matching `/llm-wiki:…` command (if any) and verify the first CLI step completes without errors.

