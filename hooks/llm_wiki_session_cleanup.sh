#!/usr/bin/env bash
# Optional: on SessionEnd, nudge stray npx / node children tied to this plugin checkout.
# OFF by default — set LLM_WIKI_CLEANUP_NPX=1 in env (e.g. ~/.claude/settings.json "env").
#
# Does NOT stop the editor MCP connection (stdio servers usually exit with the host).
# Targets only processes whose argv contains this repo path + (npx or node_modules).
set -euo pipefail

if [ "${LLM_WIKI_CLEANUP_NPX:-}" != "1" ]; then
  exit 0
fi

ROOT="${CLAUDE_PLUGIN_ROOT:-}"
if [ -z "$ROOT" ] || [ ! -d "$ROOT" ]; then
  exit 0
fi

ROOT_NORM=$(cd "$ROOT" && pwd)

# macOS pkill -f matches full command line; escape minimal regex metacharacters in path.
# Prefer SIGTERM first so well-behaved processes can exit cleanly.
_pat_npx="npx.*${ROOT_NORM}"
_pat_node_mod="node.*${ROOT_NORM}/node_modules"

pkill -TERM -f "${_pat_npx}" 2>/dev/null || true
pkill -TERM -f "${_pat_node_mod}" 2>/dev/null || true

exit 0
