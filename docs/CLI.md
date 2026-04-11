<p align="center">
  <img src="assets/readme-banner.png" alt="llm-wiki" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/SkinnnyJay/wiki-llm" title="Repository on GitHub"><img src="https://img.shields.io/badge/GitHub-repo-181717?logo=github&logoColor=white" alt="GitHub repo"/></a>
  &nbsp;
  <a href="https://github.com/SkinnnyJay/wiki-llm#install-claude-code" title="Install the plugin in Claude Code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-D4A574?logo=anthropic&logoColor=white" alt="Claude Code plugin"/></a>
  &nbsp;
  <a href="https://github.com/SkinnnyJay/wiki-llm/blob/main/AGENTS.md" title="AGENTS.md for Cursor and Codex"><img src="https://img.shields.io/badge/Cursor-rules%20%2B%20plugin-000000?logo=cursor&logoColor=white" alt="Cursor rules"/></a>
</p>


# CLI (`llm-wiki`)

**When to use this doc:** Prefer **Claude Code** (**`/llm-wiki:…`**, skills) when you are in the editor. **Full slash command list** (names, summaries, prompt paths, CLI mapping): **[`SLASH-COMMANDS.md`](./SLASH-COMMANDS.md)**. Prompt sources: [`commands/`](../commands/).

Use the **`llm-wiki`** CLI for **terminals, CI, and automation** — it mirrors the same vault operations without slash commands.

---

## Claude Code → CLI (quick map)

| In Claude Code | CLI (terminal) |
|----------------|----------------|
| `/llm-wiki:setup` | `llm-wiki setup …` |
| `/llm-wiki:ingest` | `llm-wiki ingest …` |
| `/llm-wiki:configure` | `llm-wiki configure -i` (or edit `config.json`) |
| `/llm-wiki:status` | `llm-wiki integrations status`, `llm-wiki check`, etc. |
| `/llm-wiki:memory` | `llm-wiki memory …` (when `memory.enabled`) |
| `/llm-wiki:mcp` | `llm-wiki mcp …` |

Skills (**wiki-ingest**, **wiki-research**, …) are **chat workflows**; there is not always a one-shot CLI equivalent — see [`WORKFLOWS.md`](../WORKFLOWS.md).

---

## Entrypoint and subcommands

Run **`bin/llm-wiki`** from the plugin repo (any cwd if you use the absolute path) or **`python3 scripts/llm_wiki.py`** **from the repository root**. Do **not** rely on `PYTHONPATH=scripts` with a relative path (Python 3.14+ can break); the script adds `scripts/` to `sys.path` itself.

**Common subcommands:** **`setup`**, **`ingest`**, **`validate`**, **`build-site`**, **`configure`** (`-i` interactive), **`raw validate` / `raw finish`**, **`memory …`** (when enabled), **`mcp`**, **`benchmark …`**, **`check`**, **`sync-agent-docs`**. Use **`llm-wiki --help`** and **`llm-wiki <cmd> --help`** for flags.

**Happy paths:** [`QUICKSTART.md`](./QUICKSTART.md), [`WORKFLOWS.md`](../WORKFLOWS.md). **Where commands live in code:** [`WORKFLOWS.md`](../WORKFLOWS.md) “CLI source layout”.

---

## Bash / shell

For multi-line scripts and **`./bin/llm-wiki`**, see [`INSTALL.md`](./INSTALL.md) § Bash / shell and [`QUICKSTART.md`](./QUICKSTART.md) § Bash / shell. After **`build-site`** / **`build-og`**, local preview is **`llm-wiki build-og --serve`** or **`--serve-background`**; stop the background server with **`--stop-serving`**. Or use **`./scripts/serve-viewer.sh`** — not plain **`file://`**.
