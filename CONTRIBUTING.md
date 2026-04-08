# Contributing to wiki-llm

## Pull requests and release scope

- **Keep PRs reviewable:** Prefer one cohesive change set (e.g. pipeline + tests, or docs-only) over mixing unrelated refactors with new adapters and dozens of new skills.
- **Split large work:** If you have both “core plugin behavior” and “optional ingest adapters / extract skills,” consider **two PRs** so `ingest --list`, contract tests, and reviewers stay aligned.
- **What to include before merge:** Anything that should ship together should be **committed**; untracked files are invisible to CI and to `tests/plugin_contracts.test.py` registry checks.

See also [WORKFLOWS.md](WORKFLOWS.md) (plugin development / testing).
