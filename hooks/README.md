# llm-wiki Claude Code Hooks

Two hooks that keep your vault's Memory Stack current during Claude sessions.

## `llm_wiki_precompact.sh`
Fires before Claude compresses its context window. Runs `wake-up --update-claude`
and a git snapshot so the next session starts with fresh L1 context.

## `llm_wiki_stop.sh`
Fires on every Claude stop. Updates the Memory Stack only if `wiki/` changed
since the last run — avoids no-op commits on quiet sessions.

## Setup

Add to your Claude Code settings (`~/.claude/settings.json`):

```json
{
  "hooks": {
    "PreCompact": [{
      "matcher": "",
      "hooks": [{"type": "command",
        "command": "/absolute/path/to/wiki-llm/hooks/llm_wiki_precompact.sh"}]
    }],
    "Stop": [{
      "matcher": "",
      "hooks": [{"type": "command",
        "command": "/absolute/path/to/wiki-llm/hooks/llm_wiki_stop.sh"}]
    }]
  }
}
```

Replace `/absolute/path/to/wiki-llm` with the actual path where you cloned this repo.

## Vault discovery order

1. `LLM_WIKI_VAULT` environment variable
2. `~/.llm-wiki/default-vault` (written by `llm-wiki setup`)
3. Walk up from `$PWD` looking for `llm-wiki/config.json`

If no vault is found, hooks exit 0 silently.
