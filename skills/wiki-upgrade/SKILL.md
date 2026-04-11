---
name: wiki-upgrade
description: Update the llm-wiki plugin repo (git pull), re-run setup, and sanity-check vault config against the new version.
disable-model-invocation: true
---

# Wiki upgrade — Self-update

Update the **wiki-llm** plugin checkout (this repository), re-run **`./setup`** if present, and verify the user’s **`llm-wiki/config.json`** still matches the template schema expectations. **No telemetry**.

## Pre-flight

1. Confirm the user is at the **plugin repo root** (contains **`bin/llm-wiki`**, **`scripts/llm_wiki.py`**, **`.claude-plugin/plugin.json`**). If they only have a vault, tell them to `git pull` in the plugin clone they use for development.

## Steps

### Step 1 — Fetch and merge

```bash
git status
git pull --ff-only
```

If merge conflicts or non-ff: stop and ask the user to resolve manually.

### Step 2 — Re-run setup script (optional)

If **`./setup`** exists and is executable:

```bash
chmod +x ./setup
./setup
```

This refreshes agent-specific hints (Cursor rules, etc.) per the repo root **`setup`** script.

### Step 3 — Changelog

Show **recent** changes:

```bash
git log -1 --oneline
# Optional: head CHANGELOG.md
```

### Step 4 — Vault compatibility

- Run **`python3 scripts/llm_wiki.py --help`** or **`bin/llm-wiki validate`** from repo root with **`--vault /path/to/llm-wiki`** if the user has a vault nearby.
- If **`templates/llm-wiki/config.json`** gained new keys, suggest merging defaults into the user vault’s **`config.json`** (do not overwrite without confirmation).

## Done looks like

- Plugin repo is **up to date** with `origin` (or user knows why not).
- **`./setup`** ran without fatal errors, or user skipped with reason recorded.
- User knows whether to re-run **`llm-wiki setup`** / **`wiki-setup`** for vault-only changes.

## Artifacts

Reads: git history, **`CHANGELOG.md`**, optional **`llm-wiki/config.json`**. Writes: none except user-edited files from setup.

## Related skills

- **wiki-setup** — vault reconfiguration after breaking template changes  
- **wiki-status** — verify tools after upgrade  

## Smoke check

- **CLI:** From the plugin repo root: `llm-wiki check` and `python3 -m compileall scripts` (optional syntax check).
- **Prompt:** Invoke this skill; confirm upgrade checks git remote and plugin root paths.
