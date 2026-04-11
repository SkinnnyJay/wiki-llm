# llm-wiki Claude Code Hooks

Hooks keep your vault’s Memory Stack and optional **session memory** current during Claude sessions. Definitions live in **`hooks/hooks.json`** (loaded when the plugin is installed).

## Behavior comparison

| Hook | When it runs | `wake-up` | Vault `git snapshot` | Notes |
|------|----------------|-----------|------------------------|-------|
| **PreCompact** (`llm_wiki_precompact.sh`) | Before Claude compresses context | Yes | Yes — `pre-compact checkpoint` | Automatic commit before compaction. |
| **Stop** (`llm_wiki_stop.sh`) | On each Claude stop | Yes (if `wiki/` changed or first run) | **No** | Debounced via `~/.llm-wiki/last-stop`. |
| **Stop** (`llm_wiki_memory.sh`) | On each Claude stop | No | No | Session memory: writes **`llm-wiki/.current-session`**, optional **`memory log`** (see below). |
| **PostCompact** (`llm_wiki_memory.sh`) | After compaction | No | No | Session memory: saves **`compact_summary`** when **`memory.enabled`**. |
| **SessionEnd** (`llm_wiki_memory.sh`) | End of session | No | No | Session memory: final tag save; keep work fast (default ~1.5s timeout). |
| **SessionEnd** (`llm_wiki_session_cleanup.sh`) | End of session | No | No | Opt-in (`LLM_WIKI_CLEANUP_NPX=1`): SIGTERM stray `npx`/repo `node_modules` processes for this plugin path only. |

**Session memory** is **opt-in** via **`memory.enabled`** in **`llm-wiki/config.json`**. If disabled, `llm_wiki_memory.sh` exits early after writing **`.current-session`** (harmless).

### `llm_wiki_memory.sh`

- Reads **stdin JSON** from Claude Code: **`session_id`**, **`hook_event_name`**, and event-specific fields.
- **Always** (when `session_id` is present): atomically writes **`llm-wiki/.current-session`** so **`llm-wiki memory … --current`** works without passing an id.
- **Stop:** appends a round entry via **`llm-wiki memory log --session-id … --message-preview …`** (truncated assistant preview). Skips when **`stop_hook_active`** is true to avoid loops.
- **PostCompact:** **`llm-wiki memory save`** with **`--compact-summary`** and tag **`compact`**.
- **SessionEnd:** **`llm-wiki memory save`** with tag **`session-end`**.

See **wiki-session-memory** skill and **`commands/memory.md`**.

## `llm_wiki_precompact.sh`

Fires before Claude compresses its context window. Runs `wake-up --update-claude` and a git snapshot so the next session starts with fresh L1 context.

## `llm_wiki_stop.sh`

Fires on every Claude stop. Updates the Memory Stack only if `wiki/` changed since the last run (or on first run when there is no `last-stop` file) — avoids no-op work on quiet sessions. Does **not** create a git snapshot by design.

## Setup

### Plugin install (recommended)

When llm-wiki is installed as a Claude Code plugin (marketplace install or a CLI that supports session plugin loading), hooks are **auto-loaded** from `hooks/hooks.json`. The scripts use `${CLAUDE_PLUGIN_ROOT}/bin/llm-wiki` to find the CLI — no PATH configuration needed.

### Manual install (standalone / dev clone)

If running hooks outside the plugin system, add `bin/` to your `PATH` or symlink `bin/llm-wiki`. Then add to `~/.claude/settings.json` (mirror the events in `hooks/hooks.json`, including **PostCompact**, **SessionEnd**, and the second **Stop** hook for memory):

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
      "hooks": [
        {"type": "command", "command": "/absolute/path/to/wiki-llm/hooks/llm_wiki_stop.sh"},
        {"type": "command", "command": "/absolute/path/to/wiki-llm/hooks/llm_wiki_memory.sh"}
      ]
    }],
    "PostCompact": [{
      "matcher": "",
      "hooks": [{"type": "command",
        "command": "/absolute/path/to/wiki-llm/hooks/llm_wiki_memory.sh"}]
    }],
    "SessionEnd": [{
      "matcher": "",
      "hooks": [{"type": "command",
        "command": "/absolute/path/to/wiki-llm/hooks/llm_wiki_memory.sh"}]
    }]
  }
}
```

Replace `/absolute/path/to/wiki-llm` with the actual path where you cloned this repo. The scripts fall back to `command -v llm-wiki` on PATH when `CLAUDE_PLUGIN_ROOT` is not set.

## Vault discovery order

1. `LLM_WIKI_VAULT` environment variable
2. `~/.llm-wiki/default-vault` (written by `llm-wiki setup`)
3. Walk up from `$PWD` looking for `llm-wiki/config.json`

## Permissions vs processes (`settings.local.json`)

The **`permissions.allow`** entries in **`.claude/settings.local.json`** (e.g. `Bash(npx llm-wiki:*)`) are **approval patterns** for Claude Code — they do **not** spawn or own Node/npx processes. Orphan **`npx`** / **`node`** processes usually come from **commands Claude actually ran** (or MCP / other tools), not from those JSON lines sitting in the file.

## Optional: cleanup stray npx/node on session end

**`hooks/llm_wiki_session_cleanup.sh`** runs on **SessionEnd** (after **`llm_wiki_memory.sh`**). By default it **does nothing**.

To opt in, set in **`~/.claude/settings.json`** or **`.claude/settings.local.json`** (gitignored) under **`env`**:

```json
"LLM_WIKI_CLEANUP_NPX": "1"
```

When enabled, it sends **SIGTERM** to processes whose command line matches **`npx`** plus this plugin’s **`CLAUDE_PLUGIN_ROOT`** path, or **`node`** plus **`…/node_modules`** under that path. It does **not** kill arbitrary MCP servers or unrelated projects.

If buildup continues, inspect manually: **`pgrep -fl npx`**, **`pgrep -fl node`**, then stop the editor session or kill specific PIDs — avoid broad **`pkill npx`** while other work runs.

If no vault is found, hooks exit 0 silently. If a vault is found but `llm-wiki` is not on `PATH`, see the Setup section above.
