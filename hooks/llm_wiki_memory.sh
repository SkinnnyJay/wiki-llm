#!/usr/bin/env bash
# llm_wiki_memory.sh — session memory (Stop, PostCompact, SessionEnd). Exit 0 always.
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
        if [ -f "$dir/config.json" ] && grep -q '"wiki_root"' "$dir/config.json" 2>/dev/null; then
            echo "$dir"; return
        fi
        dir=$(dirname "$dir")
    done
}

INPUT=$(cat || true)
VAULT=$(_llm_wiki_find_vault || true)
if [ -z "$VAULT" ]; then exit 0; fi

LLM_WIKI_PLUGIN_ROOT="${CURSOR_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
LLM_WIKI_BIN="${LLM_WIKI_PLUGIN_ROOT}/bin/llm-wiki"
if [ ! -x "$LLM_WIKI_BIN" ]; then
  if command -v llm-wiki >/dev/null 2>&1; then
    LLM_WIKI_BIN="llm-wiki"
  else
    exit 0
  fi
fi

if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
HOOK_EVENT=$(echo "$INPUT" | jq -r '.hook_event_name // empty')
if [ -z "$SESSION_ID" ]; then exit 0; fi

TMP=$(mktemp "$VAULT/.current-session.XXXXXX")
echo "$SESSION_ID" > "$TMP"
mv "$TMP" "$VAULT/.current-session"

if [ "$HOOK_EVENT" = "Stop" ]; then
  STOP_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
  if [ "$STOP_ACTIVE" = "true" ]; then exit 0; fi
  # Write preview to a temp file — do not pass via argv (quotes/newlines/box-drawing break shell quoting).
  PREV=$(mktemp "${TMPDIR:-/tmp}/llm_wiki_mem_preview.XXXXXX")
  trap 'rm -f "$PREV"' EXIT
  echo "$INPUT" | jq -r '.last_assistant_message // ""' > "$PREV"
  "$LLM_WIKI_BIN" --vault "$VAULT" memory log \
    --session-id "$SESSION_ID" \
    --message-preview-file "$PREV" || true
  exit 0
fi

if [ "$HOOK_EVENT" = "PostCompact" ]; then
  COMPACT_SUMMARY=$(echo "$INPUT" | jq -r '.compact_summary // empty')
  "$LLM_WIKI_BIN" --vault "$VAULT" memory save \
    --session-id "$SESSION_ID" \
    --compact-summary "$COMPACT_SUMMARY" \
    --tags "compact" || true
  exit 0
fi

if [ "$HOOK_EVENT" = "SessionEnd" ]; then
  "$LLM_WIKI_BIN" --vault "$VAULT" memory save \
    --session-id "$SESSION_ID" \
    --tags "session-end" || true
  exit 0
fi

exit 0
