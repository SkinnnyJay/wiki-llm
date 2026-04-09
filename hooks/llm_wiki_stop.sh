#!/usr/bin/env bash
# llm_wiki_stop.sh — lightweight save on Claude stop
# Only updates if wiki/ changed since last run. Exit 0 always.
set -euo pipefail

_llm_wiki_find_vault() {
    if [ -n "${LLM_WIKI_VAULT:-}" ] && [ -d "$LLM_WIKI_VAULT" ]; then
        echo "$LLM_WIKI_VAULT"; return
    fi
    local default="$HOME/.llm-wiki/default-vault"
    if [ -f "$default" ]; then
        local v; v=$(cat "$default" | tr -d '[:space:]')
        if [ -d "$v" ]; then echo "$v"; return; fi
    fi
    local dir="$PWD"
    while [ "$dir" != "/" ]; do
        if [ -f "$dir/llm-wiki/config.json" ]; then echo "$dir/llm-wiki"; return; fi
        dir=$(dirname "$dir")
    done
}

VAULT=$(_llm_wiki_find_vault || true)
if [ -z "$VAULT" ]; then exit 0; fi

LLM_WIKI_BIN="${CLAUDE_PLUGIN_ROOT:-}/bin/llm-wiki"
if [ ! -x "$LLM_WIKI_BIN" ]; then
  if command -v llm-wiki >/dev/null 2>&1; then
    LLM_WIKI_BIN="llm-wiki"
  else
    echo "llm-wiki: not found via plugin or PATH; hook skipped" >&2
    exit 0
  fi
fi

LAST_STOP="$HOME/.llm-wiki/last-stop"
WIKI_DIR="$VAULT/wiki"

# Check if wiki/ has changed since last stop (skip if first run — no last-stop file)
if [ -d "$WIKI_DIR" ] && [ -f "$LAST_STOP" ]; then
    WIKI_MTIME=$(find "$WIKI_DIR" -newer "$LAST_STOP" -name "*.md" 2>/dev/null | head -1)
    if [ -z "$WIKI_MTIME" ]; then
        exit 0  # nothing changed
    fi
fi

"$LLM_WIKI_BIN" --vault "$VAULT" wake-up --update-claude || true
"$LLM_WIKI_BIN" --vault "$VAULT" build-site --if-stale || true

# Update last-stop atomically
mkdir -p "$HOME/.llm-wiki"
TMP=$(mktemp "$HOME/.llm-wiki/last-stop.XXXXXX")
date > "$TMP"
mv "$TMP" "$LAST_STOP"

exit 0
