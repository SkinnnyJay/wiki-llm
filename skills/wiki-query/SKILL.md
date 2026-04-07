---
name: wiki-query
description: Answers questions using llm-wiki/wiki pages with citations. Use when the user asks about vault content or synthesized knowledge.
---

# Wiki query

1. Read **`wiki/index.md`**; open the most relevant `wiki/**/*.md` files.
2. Answer with **inline citations** (e.g. `` `wiki/topics/foo.md` ``).
3. If the answer should live in the vault, offer to save it as a new **wiki/** page (linked from the index) or under **outputs/** when it is a report or draft to verify before promoting to wiki.

Optional: `skills/references/context-persona.md` for tool-calling tone; vault name `persona.name` (default **Gennie**).
