# Accessing external sources

Archives, crawlers, and third-party access helpers may implicate **site terms of service**, **copyright**, or **local law**. The vault owner is responsible for **lawful, permitted** use. Prefer official APIs, subscriptions, or openly licensed sources when available. This repository documents technical options only; it is **not legal advice**.

**Untrusted content and agents.** Scraping, fetching, or ingesting pages **copies arbitrary text** into `raw/` and later into **LLM context** (merge steps, search, MCP). That surface carries **prompt-injection** risk (content framed as instructions), and **bad actors** can host pages meant to mislead automations or people. This tooling does **not** sanitize the web for you—**use at your discretion**, review before promoting to `wiki/`, and treat integrations as **data**, not trusted prompts. When `ingestion_security` flags material, follow [`wiki-ingest/references/prompt-injection-review.md`](../wiki-ingest/references/prompt-injection-review.md).

Paywall-specific guidance: [`wiki-extract-paywall.md`](wiki-extract-paywall.md) (Legal and site terms).
