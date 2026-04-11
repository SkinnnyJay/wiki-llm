# tests/skill_eval_cases.py
"""Shared skill-eval scenarios for agent smoke tests (single source of truth).

Default runner is **Claude** (`claude -p`) in ``test_skill_evals.py``. Optional **Codex**
runs live in ``test_skill_evals_codex.py`` (opt-in: ``RUN_CODEX_SKILL_EVALS=1``).

**Coverage:** every ``skills/wiki-*/SKILL.md`` appears either in ``SKILL_EVALS`` or
``SKILL_EVAL_EXCLUDE`` (network-heavy extract/research skills — see
``tests/test_plugin_inventory.py``).

**Quick runs:** ``RUN_MINIMAL_SKILL_EVALS=1`` limits Claude/Codex to three core cases
(wiki-query, wiki-status, wiki-session-memory).

Each case may include ``check_output`` (all substrings must appear) and/or ``check_output_any``
(at least one substring must appear — e.g. any adapter id from ``ingest --list``).

Codex does not mirror Claude Code’s plugin/slash-command stack; for context see:
https://blog.fsck.com/2025/10/27/skills-for-openai-codex/
"""

from __future__ import annotations

import os
from typing import Any

# Subset used when RUN_MINIMAL_SKILL_EVALS=1 (faster local iteration).
MINIMAL_SKILL_IDS: frozenset[str] = frozenset(
    {"wiki-query", "wiki-status", "wiki-session-memory"}
)

# Intentionally no ``claude -p`` smoke row: network/API or redundant with other tiers.
SKILL_EVAL_EXCLUDE: frozenset[str] = frozenset(
    {
        # Extraction (live sources / paywalls / APIs)
        "wiki-extract-annas",
        "wiki-extract-crunchbase",
        "wiki-extract-ebook",
        "wiki-extract-ecommerce",
        "wiki-extract-github",
        "wiki-extract-linkedin",
        "wiki-extract-newsletter",
        "wiki-extract-patents",
        "wiki-extract-paywall",
        "wiki-extract-podcast",
        "wiki-extract-wikipedia",
        "wiki-extract-youtube",
        "wiki-fetch",
        # Research variants that assume external web/APIs
        "wiki-research-academic",
        "wiki-research-deep",
        "wiki-research-feeds",
        "wiki-research-news",
        "wiki-research-social",
        "wiki-research-web",
    }
)

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
    {
        "skill": "wiki-lint",
        "prompt": (
            "Run `llm-wiki validate` from the vault (llm-wiki on PATH). "
            "Reply with OK or FAIL and one word from stderr if any."
        ),
        "timeout": 90,
        "check_output": ["ok"],
    },
    {
        "skill": "wiki-maintainer",
        "prompt": (
            "List two paths under wiki/ that exist in this vault. Reply with two lines, paths only."
        ),
        "timeout": 60,
        "check_output": ["wiki/"],
    },
    {
        "skill": "wiki-ingest",
        "prompt": (
            "Run `llm-wiki ingest --list`. Reply with one adapter id printed in the output."
        ),
        "timeout": 90,
        # Model may quote any line from the list; accept common adapter ids (not the word "ingest").
        "check_output_any": [
            "file",
            "url",
            "markdown",
            "pdf",
            "youtube",
            "hackernews",
            "twitter",
            "brave",
            "perplexity",
            "firecrawl",
            "ingest",
        ],
    },
    {
        "skill": "wiki-pipeline",
        "prompt": (
            "In one sentence describe the wiki-pipeline end-to-end flow; "
            "your reply must contain the word PIPELINE."
        ),
        "timeout": 90,
        "check_output": ["pipeline"],
    },
    {
        "skill": "wiki-raw-prepare",
        "prompt": (
            "In one sentence: what is raw preparation for in llm-wiki? "
            "Your reply must contain the letters RAW as substring."
        ),
        "timeout": 90,
        "check_output": ["raw"],
    },
    {
        "skill": "wiki-learn",
        "prompt": (
            "The wiki-learn skill references .agent-memory. Reply with the word LEARN "
            "and one short phrase about agent memory."
        ),
        "timeout": 60,
        "check_output": ["learn"],
    },
    {
        "skill": "wiki-retro",
        "prompt": (
            "Reply with RETRO and one sentence about what a weekly engineering retro covers."
        ),
        "timeout": 60,
        "check_output": ["retro"],
    },
    {
        "skill": "wiki-upgrade",
        "prompt": (
            "Reply with UPGRADE and one short phrase about updating the llm-wiki plugin repo (git pull)."
        ),
        "timeout": 60,
        "check_output": ["upgrade"],
    },
    {
        "skill": "wiki-research-loop",
        "prompt": (
            "Reply with LOOP and one sentence: what is a batch research-loop task list for?"
        ),
        "timeout": 90,
        "check_output": ["loop"],
    },
    {
        "skill": "wiki-research",
        "prompt": (
            "Using only files under wiki/ in this vault (no web search), "
            "name one topic page linked from wiki/index.md. Reply with RESEARCH and that filename."
        ),
        "timeout": 90,
        "check_output": ["research"],
    },
    {
        "skill": "wiki-setup",
        "prompt": (
            "Reply SETUP and answer yes or no: does `llm-wiki setup --defaults` skip the interactive wizard?"
        ),
        "timeout": 60,
        "check_output": ["setup"],
    },
]


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def skill_eval_cases_for_run() -> list[dict[str, Any]]:
    """Cases for the current run (minimal subset vs full pre-ship list)."""
    if _truthy("RUN_MINIMAL_SKILL_EVALS"):
        return [c for c in SKILL_EVALS if c["skill"] in MINIMAL_SKILL_IDS]
    return list(SKILL_EVALS)
