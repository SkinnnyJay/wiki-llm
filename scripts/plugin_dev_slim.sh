#!/usr/bin/env bash
# Shrink on-disk clutter before `claude plugin install` from a local clone.
# Local installs copy the *entire* tree into ~/.claude/plugins/cache/ (not .gitignore-aware).
# Daily dev: prefer `claude --plugin-dir /path/to/this/repo` to avoid that copy.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APPLY=0
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=1
elif [[ -n "${1:-}" ]]; then
  echo "Usage: $0 [--apply]" >&2
  echo "  (no args)  List large dev-only paths and __pycache__ dirs; no changes." >&2
  echo "  --apply    Remove those paths (safe to re-create: venvs, caches, .tmp)." >&2
  exit 1
fi

warn_claude_in_repo() {
  if [[ -d "$ROOT/.claude" ]]; then
    echo "WARNING: $ROOT/.claude exists — Claude Code may skip plugin skills/commands." >&2
    echo "  Remove or relocate it; use ~/.claude/settings.json for personal settings." >&2
    echo "  See https://github.com/anthropics/claude-code/issues/44120" >&2
  fi
}

CANDIDATES=(
  .tmp
  .venv
  .pytest_cache
  .mypy_cache
  .ruff_cache
  .tox
  .hypothesis
  node_modules
)

shopt -s nullglob
for d in .venv-*; do
  [[ -d "$d" ]] && CANDIDATES+=("$d")
done
shopt -u nullglob

echo "== plugin_dev_slim ($ROOT) =="
warn_claude_in_repo
echo ""

if [[ "$APPLY" -eq 0 ]]; then
  echo "Dry run — disk use for known dev paths (if present):"
else
  echo "Removing known dev paths:"
fi

found_any=0
for name in "${CANDIDATES[@]}"; do
  if [[ -e "$ROOT/$name" ]]; then
    found_any=1
    if [[ "$APPLY" -eq 0 ]]; then
      du -sh "$ROOT/$name" 2>/dev/null || true
    else
      echo "  rm -rf $name"
      rm -rf "${ROOT:?}/$name"
    fi
  fi
done

# __pycache__ (skip .git)
if [[ "$APPLY" -eq 0 ]]; then
  count=0
  while IFS= read -r -d '' d; do
    ((count++)) || true
  done < <(find "$ROOT" -name .git -prune -o -type d -name __pycache__ -print0 2>/dev/null)
  if [[ "$count" -gt 0 ]]; then
    found_any=1
    echo ""
    echo "__pycache__ directories ($count):"
    find "$ROOT" -name .git -prune -o -type d -name __pycache__ -print0 2>/dev/null \
      | xargs -0 du -ch 2>/dev/null | tail -1 || true
  fi
else
  while IFS= read -r -d '' d; do
    found_any=1
    rel="${d#"$ROOT"/}"
    echo "  rm -rf $rel"
    rm -rf "$d"
  done < <(find "$ROOT" -name .git -prune -o -type d -name __pycache__ -print0 2>/dev/null)
fi

# *.egg-info
if [[ "$APPLY" -eq 0 ]]; then
  count=0
  while IFS= read -r -d '' d; do
    ((count++)) || true
  done < <(find "$ROOT" -name .git -prune -o -type d -name "*.egg-info" -print0 2>/dev/null)
  if [[ "$count" -gt 0 ]]; then
    found_any=1
    echo ""
    echo "*.egg-info directories ($count):"
    find "$ROOT" -name .git -prune -o -type d -name "*.egg-info" -print0 2>/dev/null \
      | xargs -0 du -ch 2>/dev/null | tail -1 || true
  fi
else
  while IFS= read -r -d '' d; do
    found_any=1
    rel="${d#"$ROOT"/}"
    echo "  rm -rf $rel"
    rm -rf "$d"
  done < <(find "$ROOT" -name .git -prune -o -type d -name "*.egg-info" -print0 2>/dev/null)
fi

if [[ "$found_any" -eq 0 ]]; then
  echo "(nothing to trim — already slim)"
fi

echo ""
if [[ "$APPLY" -eq 0 ]]; then
  echo "Run with --apply to delete the above. Or use: claude --plugin-dir \"$ROOT\""
else
  echo "Done."
fi
