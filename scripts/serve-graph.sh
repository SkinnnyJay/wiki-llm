#!/usr/bin/env bash
# Serve the on-demand D3 graph bundle from .tmp/llm-wiki-graph/.
# Port is read from graph.port in llm-wiki/config.json (default: 8890).
#
# Usage: ./scripts/serve-graph.sh [--vault PATH]
set -euo pipefail

VAULT="${LLM_WIKI_VAULT:-llm-wiki}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vault) VAULT="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

PORT=$(python3 -c "
import json, sys
try:
    print(json.load(open('$VAULT/config.json')).get('graph', {}).get('port', 8890))
except Exception:
    print(8890)
")

DIR=".tmp/llm-wiki-graph"
if [[ ! -d "$DIR" ]]; then
  echo "Graph bundle not found at $DIR — run 'llm-wiki graph' first." >&2
  exit 1
fi

echo "→ http://127.0.0.1:$PORT/"
cd "$DIR"
exec python3 -m http.server "$PORT"
