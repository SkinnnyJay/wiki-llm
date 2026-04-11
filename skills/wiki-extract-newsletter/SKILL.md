---
name: wiki-extract-newsletter
description: Extract Substack, Beehiiv, Ghost, Buttondown newsletter issues into raw/. Handles subscriber-only content via archives, RSS, and email.
disable-model-invocation: true
argument-hint: "<newsletter URL or publication name>"
---

# Wiki extract — newsletter

**Compliance:** [`access-sources-disclaimer.md`](../references/access-sources-disclaimer.md) — fetching or ingesting issues pulls **untrusted text** into the vault (prompt-injection and bad-faith content are possible); **use at your discretion**.

Full steps, commands, frontmatter templates, and troubleshooting: **[`skills/references/wiki-extract-newsletter.md`](../references/wiki-extract-newsletter.md)**.

**Orchestration:** [`skills/wiki-extract/SKILL.md`](../wiki-extract/SKILL.md) (this index), plus **wiki-research** / **wiki-research-web** for URL routing.

## Smoke check

See **Smoke check** in [`skills/references/wiki-extract-newsletter.md`](../references/wiki-extract-newsletter.md) for **CLI** and **Prompt** verification steps.
