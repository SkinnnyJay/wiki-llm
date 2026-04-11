# tests/skill_eval_cases.py
"""Shared skill-eval scenarios for agent smoke tests (single source of truth).

Default runner is **Claude** (`claude -p`) in ``test_skill_evals.py``. Optional **Codex**
runs live in ``test_skill_evals_codex.py`` (opt-in: ``RUN_CODEX_SKILL_EVALS=1``).

Codex does not mirror Claude Code’s plugin/slash-command stack; for context see:
https://blog.fsck.com/2025/10/27/skills-for-openai-codex/
"""

from __future__ import annotations

from typing import Any

SKILL_EVALS: list[dict[str, Any]] = [
    {
        "skill": "wiki-query",
        "prompt": (
            "You are in the llm-wiki vault. Answer in 2 sentences: what do we know about "
            "authentication or OAuth? You must cite at least one path under wiki/ (e.g. wiki/auth.md)."
        ),
        "timeout": 120,
        "check_output": ["wiki/"],
    },
    {
        "skill": "wiki-status",
        "prompt": (
            "Run shell from repo: llm-wiki validate  (vault is LLM_WIKI_VAULT). "
            "Reply with one word: OK or FAIL plus one line of stderr if any."
        ),
        "timeout": 90,
        "check_output": ["ok"],
    },
    {
        "skill": "wiki-session-memory",
        "prompt": (
            "Run: llm-wiki memory list   from the vault. Reply with the first line of output only."
        ),
        "timeout": 60,
        "check_output": [],
    },
]
