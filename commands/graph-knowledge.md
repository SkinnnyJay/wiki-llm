---
description: Generate a knowledge/cluster graph — pages colored by undirected link component (relational clusters).
---

Same pipeline as **`/llm-wiki:graph`**, but uses **connected components** of the wikilink graph: pages that reach each other through links share a color (Tableau palette). Isolated pages are their own cluster.

```bash
llm-wiki graph-knowledge
# equivalent: llm-wiki graph --mode knowledge
cd .tmp/llm-wiki-graph && python3 -m http.server 8890
```

Use the sidebar legend to see cluster size and a sample title. Large wikis may have many small components until you add more cross-links.

$ARGUMENTS
