---
name: wiki-extract
description: Index and routing for source-specific vault extractors (wiki-extract-*). Use to pick which extractor or reference applies to a URL, file, or intent.
disable-model-invocation: true
argument-hint: "<source type or URL>"
---

# Wiki extract — index

**Vault extractors** live as separate **`wiki-extract-*`** skills (frontmatter for discovery) plus matching **`skills/references/wiki-extract-*.md`** files (full procedures, commands, troubleshooting).

**Prefer orchestration skills first:** **wiki-research** and **wiki-research-web** already route URLs and intents to the right extractor. Use this index when you need the routing table without opening the research skills.

## Routing (intent / pattern → skill)

| Intent or URL pattern | Skill | Full procedure |
|----------------------|--------|----------------|
| `youtube.com`, `youtu.be` | wiki-extract-youtube | [wiki-extract-youtube.md](../references/wiki-extract-youtube.md) |
| 403 / paywall / Medium / bypass | wiki-extract-paywall | [wiki-extract-paywall.md](../references/wiki-extract-paywall.md) |
| Local `.epub`, `.pdf`, `.mobi`, … | wiki-extract-ebook | [wiki-extract-ebook.md](../references/wiki-extract-ebook.md) |
| Anna's Archive, book/paper search | wiki-extract-annas | [wiki-extract-annas.md](../references/wiki-extract-annas.md) |
| Amazon, eBay, Etsy, Shopify, auctions | wiki-extract-ecommerce | [wiki-extract-ecommerce.md](../references/wiki-extract-ecommerce.md) |
| `github.com/...` repo, issue, PR | wiki-extract-github | [wiki-extract-github.md](../references/wiki-extract-github.md) |
| Substack, Beehiiv, Ghost, Buttondown | wiki-extract-newsletter | [wiki-extract-newsletter.md](../references/wiki-extract-newsletter.md) |
| `linkedin.com/...` | wiki-extract-linkedin | [wiki-extract-linkedin.md](../references/wiki-extract-linkedin.md) |
| `crunchbase.com/...` | wiki-extract-crunchbase | [wiki-extract-crunchbase.md](../references/wiki-extract-crunchbase.md) |
| `*.wikipedia.org/wiki/...` | wiki-extract-wikipedia | [wiki-extract-wikipedia.md](../references/wiki-extract-wikipedia.md) |
| Google Patents, Espacenet, USPTO | wiki-extract-patents | [wiki-extract-patents.md](../references/wiki-extract-patents.md) |
| Podcast RSS, episode pages | wiki-extract-podcast | [wiki-extract-podcast.md](../references/wiki-extract-podcast.md) |

## Environment variables

API keys and optional tools: **`docs/ENV.md`**, **`.env.example`**, and **`skills/references/preflight.md`** (integration table).

## Related

- **wiki-research** / **wiki-research-web** — primary routing and fetch orchestration
- **`skills/wiki-research/references/approaches.md`** — URL-level decision tree

## Smoke check

**CLI** and **Prompt:** Spot-check one reference (e.g. [`wiki-extract-youtube.md`](../references/wiki-extract-youtube.md)) for terminal lines and Claude Code skill invocation.
