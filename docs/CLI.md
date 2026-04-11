# CLI (`llm-wiki`)

Run **`bin/llm-wiki`** from the plugin repo (any cwd if you use the absolute path) or **`python3 scripts/llm_wiki.py`** **from the repository root**. Do **not** rely on `PYTHONPATH=scripts` with a relative path (Python 3.14+ can break); the script adds `scripts/` to `sys.path` itself.

**Common subcommands:** **`setup`**, **`ingest`**, **`validate`**, **`build-site`**, **`configure`** (`-i` interactive), **`raw validate` / `raw finish`**, **`memory …`** (when enabled), **`mcp`**, **`benchmark …`**, **`check`**, **`sync-agent-docs`**. Use **`llm-wiki --help`** and **`llm-wiki <cmd> --help`** for flags.

**Happy paths:** [`QUICKSTART.md`](./QUICKSTART.md), [`WORKFLOWS.md`](../WORKFLOWS.md). **Plugin layout (where commands live in code):** [`WORKFLOWS.md`](../WORKFLOWS.md) “CLI source layout”.
