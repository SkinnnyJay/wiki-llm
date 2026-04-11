<p align="center">
  <img src="docs/assets/readme-banner.png" alt="llm-wiki" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/SkinnnyJay/wiki-llm"><img src="https://img.shields.io/badge/GitHub-repo-181717?logo=github&logoColor=white" alt="GitHub repository"/></a>
  <a href="https://github.com/SkinnnyJay/wiki-llm/blob/main/docs/INSTALL.md#install-claude-code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-D4A574?logo=anthropic&logoColor=white" alt="Claude Code: install instructions"/></a>
  <a href="https://github.com/SkinnnyJay/wiki-llm/blob/main/AGENTS.md"><img src="https://img.shields.io/badge/Cursor-rules%20%2B%20plugin-000000?logo=cursor&logoColor=white" alt="Cursor: AGENTS.md"/></a>
</p>

# llm-wiki

**llm-wiki** is a **Claude Code plugin** (and a small Python CLI) that helps you keep a **personal knowledge vault** next to your projects: sources in **`raw/`**, curated notes in **`wiki/`**, optional **static viewer**, **MCP** search, and **session memory**—so your agent has a durable place to read and write, not a one-off chat dump.

This repository is the **plugin** (`commands/`, `skills/`, `bin/llm-wiki`). Your **vault** usually lives at **`./llm-wiki/`** in a project you choose. **Credits and lineage:** [`docs/INSPIRATION.md`](docs/INSPIRATION.md). **Branding / images (C2PA):** [`docs/ASSETS.md`](docs/ASSETS.md).

---

## Get started

**Claude Code (recommended):** install the plugin, run **`/reload-plugins`**, then **`/llm-wiki:setup`**. Use **`/llm-wiki:status`**, **`/llm-wiki:ingest`**, and skills such as **wiki-ingest**, **wiki-maintainer**, and **wiki-pipeline** for day-to-day work. Full steps: **[`docs/INSTALL.md`](docs/INSTALL.md)**.

**Cursor / Codex:** **[`AGENTS.md`](AGENTS.md)** and **[`rules/llm-wiki.mdc`](rules/llm-wiki.mdc)** — use **`commands/*.md`** as prompts (same text as **`/llm-wiki:…`**).

**CLI or CI:** **[`docs/CLI.md`](docs/CLI.md)** and **[`docs/QUICKSTART.md`](docs/QUICKSTART.md)**.

---

## Documentation

| Topic | Doc |
|-------|-----|
| Install, reload, slash-first vs dev clone | [`docs/INSTALL.md`](docs/INSTALL.md) |
| Five-minute path, tiers, feature map | [`docs/QUICKSTART.md`](docs/QUICKSTART.md) |
| Day-to-day flows, green path, troubleshooting | [`WORKFLOWS.md`](WORKFLOWS.md) |
| Evidence and trust (`raw/` vs `wiki/`) | [`ETHOS.md`](ETHOS.md) |
| `config.json` and hooks | [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) |
| Env vars and integrations | [`docs/ENV.md`](docs/ENV.md), [`.env.example`](.env.example) |
| Slash prompts | [`commands/`](commands/) |
| Skills | [`skills/`](skills/) |
| MCP, search, knowledge graph | [`skills/references/mcp-and-kg.md`](skills/references/mcp-and-kg.md) |
| Benchmarks | [`benchmarks/README.md`](benchmarks/README.md) |
| GitHub Pages site | [`docs/README.md`](docs/README.md), [`docs/PUBLISHING.md`](docs/PUBLISHING.md) |
| Contributing, tests | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Shared agent text (sync) | [`docs/AGENTS.shared.md`](docs/AGENTS.shared.md) |

**Persona:** [`prompts/PERSONA.md`](prompts/PERSONA.md), [`agents/`](agents/). **Marketplace entry:** [`marketplace.json`](marketplace.json).

---

## Privacy

No phone-home telemetry from the plugin. Optional APIs (Firecrawl, Perplexity, etc.) use **your** keys. Vault and session memory stay **local** unless you sync them yourself.

---

## License

MIT — see [LICENSE](LICENSE).
