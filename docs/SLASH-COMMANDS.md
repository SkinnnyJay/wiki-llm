<p align="center">
  <img src="assets/readme-banner.png" alt="llm-wiki" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/SkinnnyJay/wiki-llm"><img src="https://img.shields.io/badge/GitHub-repo-181717?logo=github&logoColor=white" alt="GitHub repository"/></a>
  <a href="https://github.com/SkinnnyJay/wiki-llm#install-claude-code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-D4A574?logo=anthropic&logoColor=white" alt="Claude Code: install instructions"/></a>
  <a href="https://github.com/SkinnnyJay/wiki-llm/blob/main/AGENTS.md"><img src="https://img.shields.io/badge/Cursor-rules%20%2B%20plugin-000000?logo=cursor&logoColor=white" alt="Cursor: AGENTS.md"/></a>
</p>


# Slash commands (`/llm-wiki:…`)

In **Claude Code**, each **`/llm-wiki:<name>`** slash command uses the **same prompt text** as the matching file **`commands/<name>.md`** in this repository. **Cursor / Codex:** open those files (or use [`AGENTS.md`](../AGENTS.md)) — there is no plugin install.

**Order:** prefer slash commands + **skills** in chat; use the **`llm-wiki`** **CLI** for terminals and CI; **bash** recipes live in [`INSTALL.md`](./INSTALL.md) and [`QUICKSTART.md`](./QUICKSTART.md). CLI mapping: [`CLI.md`](./CLI.md).

---

## Index (all commands)

| Slash command | Prompt file | Summary |
|---------------|-------------|---------|
| `/llm-wiki:setup` | [`commands/setup.md`](../commands/setup.md) | Vault and/or session-memory setup wizard; full body in **wiki-setup** skill. |
| `/llm-wiki:configure` | [`commands/configure.md`](../commands/configure.md) | Post-setup config — MCP `wiki_configure`, `llm-wiki configure -i`, or wizard sections. |
| `/llm-wiki:status` | [`commands/status.md`](../commands/status.md) | Vault health: setup flag, integrations, MCP search/KG; **wiki-status** skill. |
| `/llm-wiki:ingest` | [`commands/ingest.md`](../commands/ingest.md) | Ingest into `raw/` via any adapter, then merge with **wiki-ingest**. |
| `/llm-wiki:raw-prepare` | [`commands/raw-prepare.md`](../commands/raw-prepare.md) | Validate/clean `raw/`, preparation log, optional `[prepare]` git commit. |
| `/llm-wiki:integrations` | [`commands/integrations.md`](../commands/integrations.md) | Optional integrations (Firecrawl, Playwright, keys, adapters). |
| `/llm-wiki:query` | [`commands/query.md`](../commands/query.md) | Answer from the wiki with citations; optional write-back to `wiki/`. |
| `/llm-wiki:lint` | [`commands/lint.md`](../commands/lint.md) | Wiki health — orphans, gaps, contradictions (**wiki-lint**). |
| `/llm-wiki:research` | [`commands/research.md`](../commands/research.md) | Ad-hoc topic research → `raw/` → `wiki/` (**wiki-research**). |
| `/llm-wiki:research-loop` | [`commands/research-loop.md`](../commands/research-loop.md) | Batch tasks from `research-tasks.json` / YAML (**wiki-research-loop**). |
| `/llm-wiki:build-og` | [`commands/build-og.md`](../commands/build-og.md) | Static viewer + `wiki-data.json` under `wiki/.og/` (`llm-wiki build-site`). |
| `/llm-wiki:graph` | [`commands/graph.md`](../commands/graph.md) | D3 wikilink graph → `.tmp/llm-wiki-graph/`. |
| `/llm-wiki:graph-knowledge` | [`commands/graph-knowledge.md`](../commands/graph-knowledge.md) | Cluster / component view of the same graph bundle. |
| `/llm-wiki:git-status` | [`commands/git-status.md`](../commands/git-status.md) | Vault-scoped `git status` (`git.enabled`). |
| `/llm-wiki:git-log` | [`commands/git-log.md`](../commands/git-log.md) | Vault-scoped log. |
| `/llm-wiki:git-diff` | [`commands/git-diff.md`](../commands/git-diff.md) | Vault working tree / staged diff. |
| `/llm-wiki:git-snapshot` | [`commands/git-snapshot.md`](../commands/git-snapshot.md) | Commit vault state with a message. |
| `/llm-wiki:git-lifecycle` | [`commands/git-lifecycle.md`](../commands/git-lifecycle.md) | Audit commits by lifecycle phase (`llm-wiki git lifecycle`). |
| `/llm-wiki:memory` | [`commands/memory.md`](../commands/memory.md) | Session memory under `raw/memory/` when `memory.enabled` (**wiki-session-memory**). |
| `/llm-wiki:mcp` | [`commands/mcp.md`](../commands/mcp.md) | MCP server — stdio or HTTP; search/KG backends per `config.json`. |
| `/llm-wiki:benchmark` | [`commands/benchmark.md`](../commands/benchmark.md) | Retrieval benchmarks (LME / LoCoMo / ConvoMem); `llm-wiki benchmark …`. |

---

## Details

- **Full text** of each command is the body of the linked **`.md`** file after the YAML frontmatter (where present).
- **Skills** (`skills/*/SKILL.md`) add orchestration and conventions; slash commands are the **prompt surface** in Claude Code.
- **Adding a command:** add **`commands/<name>.md`**, wire the plugin manifest if required, and extend [`CLI.md`](./CLI.md) / this table if there is a CLI equivalent.

**See also:** [`WORKFLOWS.md`](../WORKFLOWS.md), [`CLI.md`](./CLI.md), [`skills/references/mcp-and-kg.md`](../skills/references/mcp-and-kg.md).
