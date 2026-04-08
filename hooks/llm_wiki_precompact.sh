#!/usr/bin/env bash
# llm_wiki_precompact.sh — emergency save before Claude context compression
# Exit code MUST be 0 always (a failing hook must not interrupt Claude).
set -euo pipefail

_llm_wiki_find_vault() {
    # Priority: env var > ~/.llm-wiki/default-vault > walk $PWD
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

VAULT=$(_llm_wiki_find_vault || true)
if [ -z "$VAULT" ]; then exit 0; fi

LLM_WIKI_BIN="${CLAUDE_PLUGIN_ROOT:-}/bin/llm-wiki"
if [ ! -x "$LLM_WIKI_BIN" ]; then
  # Fallback to PATH (standalone install or dev clone)
  if command -v llm-wiki >/dev/null 2>&1; then
    LLM_WIKI_BIN="llm-wiki"
  else
    echo "llm-wiki: not found via plugin or PATH; hook skipped" >&2
    exit 0
  fi
fi

"$LLM_WIKI_BIN" --vault "$VAULT" wake-up --update-claude || true
"$LLM_WIKI_BIN" --vault "$VAULT" git snapshot --phase wiki -m "pre-compact checkpoint" || true

exit 0
