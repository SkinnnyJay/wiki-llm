# Minimal example vault

This directory is a **small working vault** (same layout as `llm-wiki setup` produces): `wiki/`, `raw/`, `config.json`, `CLAUDE.md`.

## Use it

- **Copy** into your repo as **`llm-wiki/`** (rename this folder), then run:

  ```sh
  llm-wiki --vault llm-wiki validate --wikilinks
  llm-wiki --vault llm-wiki build-site
  ```

- Or **scaffold fresh** with `llm-wiki setup --root . --defaults` and use this folder only as a reference.

`config.json` keeps **`git.enabled`: false** and **`benchmark.enabled`: false** to stay small. Network-capable integrations and MCP write tools are deliberately off; enable only the integration or capability you intend to use after reviewing its configuration.

See **[`docs/QUICKSTART.md`](../../docs/QUICKSTART.md)** in the plugin repo.
