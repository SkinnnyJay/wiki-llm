#!/usr/bin/env bash
# Serve the static wiki viewer from llm-wiki/wiki/.og/.
# Port is read from viewer.port in llm-wiki/config.json (default: 8765).
#
# Usage: ./scripts/serve-viewer.sh [--vault PATH]
set -euo pipefail

VAULT="${LLM_WIKI_VAULT:-llm-wiki}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vault) VAULT="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

PORT=$(python3 -c "
import json
try:
    print(json.load(open('$VAULT/config.json')).get('viewer', {}).get('port', 8765))
except Exception:
    print(8765)
")

DIR="$VAULT/wiki/.og"
if [[ ! -d "$DIR" ]]; then
  echo "Viewer not found at $DIR — run 'llm-wiki build-site' first." >&2
  exit 1
fi

echo "→ http://127.0.0.1:$PORT/"
cd "$DIR"
exec python3 -m http.server "$PORT"
