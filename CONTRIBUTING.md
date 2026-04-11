# Contributing to wiki-llm

## Pull requests and release scope

- **Maintainer backlog:** Track follow-ups in issues or your team’s tool of choice (no separate `TODOS.md` in-repo).
- **Keep PRs reviewable:** Prefer one cohesive change set (e.g. pipeline + tests, or docs-only) over mixing unrelated refactors with new adapters and dozens of new skills.
- **Split large work:** If you have both “core plugin behavior” and “optional ingest adapters / extract skills,” consider **two PRs** so `ingest --list`, contract tests, and reviewers stay aligned.
- **What to include before merge:** Anything that should ship together should be **committed**; untracked files are invisible to CI and to `tests/plugin_contracts.test.py` registry checks.

See also [WORKFLOWS.md](WORKFLOWS.md) (plugin development / testing, including where CLI commands live under `scripts/cli/`).

## Before merge or release (plugin repo)

From the repository root:

1. **`bin/llm-wiki sync-agent-docs --check`** — fails if `AGENTS.md`, `CLAUDE.md`, or `rules/llm-wiki.mdc` drift from [`docs/AGENTS.shared.md`](docs/AGENTS.shared.md). Fix with **`bin/llm-wiki sync-agent-docs`** and commit.
2. **`bin/llm-wiki check --plugin-repo`** — runs the same agent-doc verification (quiet on success), **`compileall`** on `scripts/`, and is what CI runs before pytest.
3. **`bin/llm-wiki smoke-test`** — full test suite (or **`--only-contracts`** for a faster gate).

**Python versions:** CI runs pytest on **3.12** and **3.14** (see [`.github/workflows/tests.yml`](.github/workflows/tests.yml)). To match CI locally, create a venv (`python3.14 -m venv .venv`), install **`requirements-dev.txt`**, then from the repo root run **`bin/llm-wiki smoke-test`** or **`python3 -m pytest tests/`** with **`PYTHONPATH=scripts`** if you invoke pytest directly. Prefer **`python3 scripts/llm_wiki.py`** or **`bin/llm-wiki`** for CLI entry — they adjust **`sys.path`** without fragile relative **`PYTHONPATH`** (especially on Python 3.14+).

Version bumps in [CHANGELOG.md](CHANGELOG.md) should ship with a green CI run on `main` / your release branch.

## Publishing (maintainers)

- **Docs site & marketplace checks:** [docs/PUBLISHING.md](docs/PUBLISHING.md) (GitHub Pages from `/docs`, public repo for marketplace installs, post-publish smoke).
- **Tracked files:** Do not tag a release with changes that should be in git but are still untracked — CI and `tests/plugin_contracts.test.py` only see committed files.

## OpenAI Codex marketplace

Third-party **Codex** plugin submission may be limited while the ecosystem matures. This repo already ships [`.codex/config.toml`](.codex/config.toml) and root [`AGENTS.md`](AGENTS.md) for Codex CLI discovery. When submissions open, follow [OpenAI’s Codex plugin docs](https://developers.openai.com/codex/plugins/) and add a short note here.

## Telemetry

The plugin **does not** include built-in analytics. Marketplace hosts (Anthropic, Cursor, etc.) may provide their own install or usage statistics according to their terms — that is outside this repository’s code.
