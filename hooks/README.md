# llm-wiki Claude Code Hooks

Two hooks that keep your vault's Memory Stack current during Claude sessions.

## Behavior comparison

| Hook | When it runs | `wake-up` | Vault `git snapshot` | Notes |
|------|----------------|-----------|------------------------|--------|
| **PreCompact** (`llm_wiki_precompact.sh`) | Before Claude compresses context | Yes | Yes — `pre-compact checkpoint` | Use when you want an automatic commit before compaction. |
| **Stop** (`llm_wiki_stop.sh`) | On each Claude stop | Yes (if `wiki/` changed or first run) | **No** | Debounced via `~/.llm-wiki/last-stop`; avoids noisy commits. For a commit on stop, run [`llm-wiki git snapshot`](../commands/git-snapshot.md) manually or rely on PreCompact. |

## `llm_wiki_precompact.sh`

Fires before Claude compresses its context window. Runs `wake-up --update-claude` and a git snapshot so the next session starts with fresh L1 context.

## `llm_wiki_stop.sh`

Fires on every Claude stop. Updates the Memory Stack only if `wiki/` changed since the last run (or on first run when there is no `last-stop` file) — avoids no-op work on quiet sessions. Does **not** create a git snapshot by design.

## Setup

### Plugin install (recommended)

When llm-wiki is installed as a Claude Code plugin (marketplace or `--plugin-dir`), hooks are **auto-loaded** from `hooks/hooks.json`. The scripts use `${CLAUDE_PLUGIN_ROOT}/bin/llm-wiki` to find the CLI — no PATH configuration needed.

### Manual install (standalone / dev clone)

If running hooks outside the plugin system, add `bin/` to your `PATH` or symlink `bin/llm-wiki`. Then add to `~/.claude/settings.json`:

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

Replace `/absolute/path/to/wiki-llm` with the actual path where you cloned this repo. The scripts fall back to `command -v llm-wiki` on PATH when `CLAUDE_PLUGIN_ROOT` is not set.

## Vault discovery order

1. `LLM_WIKI_VAULT` environment variable
2. `~/.llm-wiki/default-vault` (written by `llm-wiki setup`)
3. Walk up from `$PWD` looking for `llm-wiki/config.json`

If no vault is found, hooks exit 0 silently. If a vault is found but `llm-wiki` is not on `PATH`, see the Setup section above.
