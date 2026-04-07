---
description: Build static graph viewer + wiki-data.json into llm-wiki/wiki/.og/
---

Run:

```bash
llm-wiki build-site
```

(alias: `llm-wiki build-og`)

Respects `viewer.enabled`. Serve with:

```bash
cd llm-wiki/wiki/.og && python3 -m http.server 8765
```

$ARGUMENTS
