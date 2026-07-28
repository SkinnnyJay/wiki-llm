#!/usr/bin/env bash
# Serve the on-demand D3 graph bundle from .tmp/llm-wiki-graph/.
# Port is read from graph.port in llm-wiki/config.json (default: 8890).
#
# Usage: ./scripts/serve-graph.sh [--vault PATH]
set -euo pipefail

VAULT="${LLM_WIKI_VAULT:-llm-wiki}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vault)
      [[ $# -ge 2 ]] || { echo "--vault requires a path" >&2; exit 2; }
      VAULT="$2"
      shift 2
      ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ ! -d "$VAULT" ]]; then
  echo "Vault not found: $VAULT" >&2
  exit 1
fi
VAULT="$(cd "$VAULT" && pwd)"

PORT=$(python3 - "$VAULT" <<'PY'
import json
import sys

try:
    with open(f"{sys.argv[1]}/config.json", encoding="utf-8") as config:
        print(json.load(config).get("graph", {}).get("port", 8890))
except Exception:
    print(8890)
PY
)

DIR="$VAULT/.tmp/llm-wiki-graph"
if [[ ! -d "$DIR" ]]; then
  echo "Graph bundle not found at $DIR — run 'llm-wiki graph' first." >&2
  exit 1
fi

echo "→ http://127.0.0.1:$PORT/"
exec python3 -m http.server "$PORT" --directory "$DIR"
