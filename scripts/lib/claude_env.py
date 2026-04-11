"""Environment helpers for Claude Code CLI subprocesses.

When ``ANTHROPIC_API_KEY`` (and similar) are present, the ``claude`` binary
typically uses API / pay-as-you-go billing. For Claude Code **subscription**
and OAuth / keychain login, omit those variables so the CLI matches interactive
``claude`` behavior.

``~/.claude/settings.json`` can still inject the same keys via merged ``env``;
use ``--setting-sources`` (see ``tests/conftest.py`` ``claude_runner``) to avoid
that layer when you want subscription auth.
"""

from __future__ import annotations

# Env vars that steer the CLI toward API-key auth / API usage billing.
ANTHROPIC_API_CREDENTIAL_ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
)


def strip_anthropic_api_credentials(env: dict[str, str]) -> dict[str, str]:
    """Return a copy of ``env`` with API credential keys removed."""
    out = dict(env)
    for k in ANTHROPIC_API_CREDENTIAL_ENV_VARS:
        out.pop(k, None)
    return out
