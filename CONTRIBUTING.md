# Contributing to wiki-llm

## Pull requests and release scope

- **Keep PRs reviewable:** Prefer one cohesive change set (e.g. pipeline + tests, or docs-only) over mixing unrelated refactors with new adapters and dozens of new skills.
- **Split large work:** If you have both “core plugin behavior” and “optional ingest adapters / extract skills,” consider **two PRs** so `ingest --list`, contract tests, and reviewers stay aligned.
- **What to include before merge:** Anything that should ship together should be **committed**; untracked files are invisible to CI and to `tests/plugin_contracts.test.py` registry checks.

See also [WORKFLOWS.md](WORKFLOWS.md) (plugin development / testing).

## Before merge or release (plugin repo)

From the repository root:

1. **`bin/llm-wiki sync-agent-docs --check`** — fails if `AGENTS.md`, `CLAUDE.md`, `rules/llm-wiki.mdc`, or `.claude/rules/llm-wiki.md` drift from [`docs/AGENTS.shared.md`](docs/AGENTS.shared.md). Fix with **`bin/llm-wiki sync-agent-docs`** and commit.
2. **`bin/llm-wiki check --plugin-repo`** — runs the same agent-doc verification (quiet on success), **`compileall`** on `scripts/`, and is what CI runs before pytest.
3. **`bin/llm-wiki smoke-test`** — full test suite (or **`--only-contracts`** for a faster gate).

Version bumps in [CHANGELOG.md](CHANGELOG.md) should ship with a green CI run on `main` / your release branch.
