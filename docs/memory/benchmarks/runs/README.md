<p align="center">
  <img src="../../../assets/readme-banner.png" alt="llm-wiki" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/SkinnnyJay/wiki-llm" title="Repository on GitHub"><img src="https://img.shields.io/badge/GitHub-repo-181717?logo=github&logoColor=white" alt="GitHub repo"/></a>
  &nbsp;
  <a href="https://github.com/SkinnnyJay/wiki-llm#install-claude-code" title="Install the plugin in Claude Code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-D4A574?logo=anthropic&logoColor=white" alt="Claude Code plugin"/></a>
  &nbsp;
  <a href="https://github.com/SkinnnyJay/wiki-llm/blob/main/AGENTS.md" title="AGENTS.md for Cursor and Codex"><img src="https://img.shields.io/badge/Cursor-rules%20%2B%20plugin-000000?logo=cursor&logoColor=white" alt="Cursor rules"/></a>
</p>


# Run artifacts (JSON + optional Markdown)

**JSON** — Store benchmark summary snapshots you care to version (LME experiments, mode compares, “best so far” rows) as small **`*.json`** files in this folder. Prefer concise, reviewable files; regenerate after serious runs instead of committing every trial.

**Hygiene:** Use **paths relative to the repo root** inside JSON (e.g. `scripts/.tmp/...` for local failure logs), not absolute machine paths (`/Volumes/...`, `/Users/...`), so clones stay portable.

**Markdown (optional)** — Add milestone write-ups (scores, deltas vs a previous run, config notes) as needed. The CLI records metrics in the vault **`.metrics.jsonl`** and can optionally append to **`docs/memory/benchmarks/metrics/runs.jsonl`** when **`benchmark.append_repo_runs_jsonl`** is enabled in **`config.json`** — see [`docs/memory/benchmarks/metrics/README.md`](../metrics/README.md). This **`runs/`** directory is for narratives and JSON you want in git beside each other.

For how to run benchmarks and read scores, see **[`benchmarks/README.md`](../../../../benchmarks/README.md)** in the plugin repo root.
