---
description: Configure optional ingest integrations (API keys via env, dependency checks).
---

# Integrations wizard

1. Load `llm-wiki/config.json` and explain each optional adapter (Firecrawl, MarkItDown, YouTube, etc.).
2. Run:

```bash
llm-wiki integrations status
```

3. For each integration the user wants, set `integrations.<id>.enabled` and document the **environment variable** for API keys (never commit secrets). Update `config.json` accordingly.
4. Run:

```bash
llm-wiki integrations validate
```

5. CLI quick reference: `llm-wiki integrations wizard` prints the same steps for terminal-only use.

Resolve failures by installing optional Python packages or setting env vars.

User context: $ARGUMENTS
