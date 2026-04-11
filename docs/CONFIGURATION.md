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


# Configuration

**Order:** **Claude Code** → **CLI** → **config file** details.

<a id="configuration-full"></a>

## 1. Claude Code

- **`/llm-wiki:configure`** — guided tweaks to **`llm-wiki/config.json`** (same ideas as [`commands/configure.md`](../commands/configure.md)).

## 2. CLI

- **`llm-wiki configure -i`** — interactive edits from a terminal.

## 3. `config.json` (reference)

Toggles live in **`llm-wiki/config.json`**: viewer, integrations, git, research loop, ingestion security, optional hooks, and **`persona.name`** (default **Gennie**). For sound hooks, ingest policy, viewer serving, and git lifecycle, see **[`WORKFLOWS.md`](../WORKFLOWS.md)**.

### Quick reference

- **`config.json`** — `viewer` (including `open_file_scheme`, `og_base_url`), `integrations`, `git`, `research_loop`, `ingestion_security`, **`hooks.sound`**, **`persona.name`**.
- **Sound hook** — Optional `hooks.sound.enabled` + `hooks.sound.command` (argv JSON); restrict executables unless `allow_arbitrary_command` is set deliberately (see **WORKFLOWS**).
- **Ingest URLs** — `ingest url` / Firecrawl allow http(s) to public hosts only; integration hosts are allowlisted.
- **Viewer** — Serve `wiki/.og/` over HTTP; **DOMPurify** on rendered bodies; **Open file** via `viewer.open_file_scheme`.
- **Ingest paths** — `--out` must stay under `raw/`.
- **Wikilinks** — `[[Page]]` / `[[page.md|label]]`; general Markdown: [Markdown Guide](https://www.markdownguide.org/basic-syntax/).
- **Vault git** — With `git.enabled`, **`llm-wiki git lifecycle`** audits commits by phase; see [`commands/git-lifecycle.md`](../commands/git-lifecycle.md).
