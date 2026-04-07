---
description: Audit vault git history by lifecycle phase (ingest, wiki, build, …) for flow progression.
---

Vault-scoped git only (`git.enabled`). Uses **subject-line prefixes** from `llm-wiki/config.json` → `git.lifecycle.phases` (default `[ingest]`, `[wiki]`, `[build]`, …). Commits that match none are labeled `unlabeled`.

**List recent commits with phase:**

```bash
llm-wiki git lifecycle -n 40
```

**Filter to one phase (e.g. only ingest snapshots):**

```bash
llm-wiki git lifecycle --phase ingest -n 50
```

**Machine-readable (agents, dashboards):**

```bash
llm-wiki git lifecycle --json -n 100
```

**Since a date:**

```bash
llm-wiki git lifecycle --since="2 weeks ago" --phase wiki
```

**Manual snapshot with a phase prefix:**

```bash
llm-wiki git snapshot -m "merged HN notes" --phase wiki
```

Optional: `git.snapshot_after_build` auto-snapshots after `build-site` (updates `wiki/.og/`). For on-demand graphs under `.tmp/`, use **`git snapshot -m "…" --phase graph`** manually if you want that step in the audit trail.

$ARGUMENTS
