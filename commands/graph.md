---
description: Generate an on-demand D3 link graph of llm-wiki/wiki into .tmp/llm-wiki-graph (GitHub-dark styled).
---

1. Run from the project root (vault discoverable via `./llm-wiki` or `LLM_WIKI_VAULT`):

```bash
llm-wiki graph
```

2. Serve the output (required for `fetch(graph-data.json)` in the browser):

```bash
cd .tmp/llm-wiki-graph && python3 -m http.server 8890
```

3. Open `http://127.0.0.1:8890/` — **links** mode: node size ∝ degree, color ∝ connectivity (blues). Pan/zoom and drag nodes.

4. Optional: `--out /other/dir` to change the output folder.

$ARGUMENTS
