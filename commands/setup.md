---
description: Run the llm-wiki vault setup wizard — paths, config.json, optional git init.
---

# Setup LLM Wiki vault

1. Ask the user for `viewer.og_base_url` (optional) and whether to enable **vault git**, **research loop**, and **ingestion security** (defaults are in `llm-wiki/config.json`).
2. Run from the project root:

```bash
llm-wiki configure -i
```

Or non-interactive flags:

```bash
llm-wiki configure --og-base-url "https://example.com/wiki" --git-enabled true
```

3. Scaffold the vault if missing:

```bash
llm-wiki setup --root .
```

4. Optionally append to the **repository root** `CLAUDE.md` one line: `See llm-wiki/CLAUDE.md for wiki maintainer rules.`

Use `$ARGUMENTS` for any extra user notes (optional).
