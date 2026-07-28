#!/usr/bin/env bash
# Serve the static wiki viewer from llm-wiki/wiki/.og/.
# Port is read from viewer.port in llm-wiki/config.json (default: 8765).
#
# Usage: ./scripts/serve-viewer.sh [--vault PATH]
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
        print(json.load(config).get("viewer", {}).get("port", 8765))
except Exception:
    print(8765)
PY
)

DIR="$VAULT/wiki/.og"
if [[ ! -d "$DIR" ]]; then
  echo "Viewer not found at $DIR — run 'llm-wiki build-site' first." >&2
  exit 1
fi

echo "→ http://127.0.0.1:$PORT/"
exec python3 -m http.server "$PORT" --directory "$DIR"
