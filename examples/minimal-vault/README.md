# Minimal example vault

This directory is a **small working vault** (same layout as `llm-wiki setup` produces): `wiki/`, `raw/`, `config.json`, `CLAUDE.md`.

## Use it

- **Copy** into your repo as **`llm-wiki/`** (rename this folder), then run `llm-wiki validate` and `llm-wiki build-site` with `--vault` pointing at it.
- Or **scaffold fresh** with `llm-wiki setup --root . --defaults` and use this folder only as a reference.

`config.json` here sets **`git.enabled`: false** and **`benchmark.enabled`: false** to keep the example simple; turn them on when you need history or retrieval benchmarks.

See **[`docs/QUICKSTART.md`](../../docs/QUICKSTART.md)** in the plugin repo.
