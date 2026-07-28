# llm-wiki product brief

llm-wiki is a local-first knowledge-vault plugin and Python CLI. It turns source material into maintainable Markdown that an agent can navigate without treating a chat transcript as a database.

## The workflow

1. Capture files, URLs, or notes in `raw/`.
2. Review and curate them into linked pages in `wiki/`.
3. Validate, search, and optionally publish a static viewer.

The vault stays in your filesystem and can be versioned with Git. Session memory is optional and remains separate from durable wiki knowledge.

## What it includes

- Claude Code slash commands and agent skills for the curation workflow.
- `llm-wiki` CLI for setup, ingest, validation, viewer builds, knowledge-graph operations, session memory, and retrieval benchmarks.
- MCP access so supported agent hosts can search the vault and use its tools.

## Design boundary

Ingested material is untrusted until reviewed. `raw/` preserves source evidence; `wiki/` is the curated layer you stand behind. See the [threat model](./THREAT-MODEL.md) and [ethos](../ETHOS.md) for the trust model.

## Start

Follow the [five-minute quickstart](./QUICKSTART.md), then use [`WORKFLOWS.md`](../WORKFLOWS.md) for the day-to-day loop.
