# Pre-ship checklist

Use before tagging a release. Check items off in the PR/release notes; leave a short note when something is intentionally skipped.

## [0.3.0] — 2026-07-28

- [x] Review the threat model for the release (`docs/THREAT-MODEL.md` reviewed; trust boundaries and Phase 1 exclusions still accurate).
- [x] Confirm path-validation, SSRF, and MCP test suites are green (`tests/test_path_escape.py`, `tests/test_safe_fetch.py`, `tests/test_mcp_contract.py`; full suite 319 passed locally).
- [x] Skill-evals: credentialed Claude skill-evals were **not** run for this tag (`ANTHROPIC_API_KEY` not configured in local/CI secrets). Workflow [`.github/workflows/skill-evals.yml`](../.github/workflows/skill-evals.yml) remains scheduled/manual; re-run before the next major when the secret is available.
- [x] Verify marketplace links resolve to [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) (present; README points at it).
- [x] Update version notes and create the matching release tag (`v0.3.0`).

## Template (next release)

- [ ] Review the threat model for the release.
- [ ] Confirm path-validation, SSRF, and MCP test suites are green.
- [ ] Before a major release, confirm the scheduled/manual skill-evals workflow is green (or record why credentialed evaluation was unavailable).
- [ ] Verify marketplace links resolve to [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json).
- [ ] Update version notes and create the matching release tag after the release commit is approved.
