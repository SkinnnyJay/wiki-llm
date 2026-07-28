# tests/plugin_contracts.test.py
"""Static contracts: commands/skills markdown, CLI mentions, smoke sections, ingest registry."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

from ingest.adapters import ADAPTERS  # noqa: E402
from ingest.registry import adapter_map  # noqa: E402
from lib.sitegen import _simple_frontmatter  # noqa: E402

WIKI_SKILL = re.compile(r"\*\*(wiki-[a-z0-9-]+)\*\*")
LLM_WIKI_INLINE = re.compile(r"`(llm-wiki\s+[^`]+)`")
LLM_WIKI_FENCE = re.compile(r"^```(?:bash|sh|zsh)?\s*$([\s\S]*?)^```", re.MULTILINE)


def _scan_llm_wiki_tokens(text: str) -> list[str]:
    """Extract first shell token after llm-wiki from backticks and bash fences."""
    out: list[str] = []
    for m in LLM_WIKI_INLINE.finditer(text):
        line = m.group(1).strip()
        if line.startswith("llm-wiki"):
            rest = line[len("llm-wiki") :].strip()
            if rest:
                out.append(rest.split()[0])
    for m in LLM_WIKI_FENCE.finditer(text):
        block = m.group(1)
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("llm-wiki"):
                rest = line[len("llm-wiki") :].strip()
                if rest:
                    out.append(rest.split()[0])
    return out


@pytest.fixture(scope="module")
def top_level_cli() -> set[str]:
    from llm_wiki import build_parser  # noqa: E402

    from lib.cli_spec import top_level_subcommands  # noqa: E402

    return top_level_subcommands(build_parser())


def test_adapter_registry_matches_adapters_list():
    ids = {cls.id for cls in ADAPTERS}
    reg = set(adapter_map().keys())
    assert ids == reg, f"ADAPTERS vs adapter_map mismatch: {ids ^ reg}"


def test_ingest_list_stdout_matches_registry():
    import os
    import subprocess

    llm_wiki = REPO / "scripts" / "llm_wiki.py"
    env = os.environ.copy()
    p = str(REPO / "scripts")
    env["PYTHONPATH"] = p + os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else p
    r = subprocess.run(
        [sys.executable, str(llm_wiki), "ingest", "--list"],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    out = r.stdout
    for aid in sorted(adapter_map().keys()):
        assert aid in out, f"ingest --list missing adapter {aid!r}"


def test_every_command_has_frontmatter_and_description():
    for path in sorted((REPO / "commands").glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, body = _simple_frontmatter(text)
        assert fm.get("description"), f"{path.name}: missing description in frontmatter"
        assert body.strip(), f"{path.name}: empty body"


def test_every_skill_has_name_and_description():
    for path in sorted((REPO / "skills").glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, body = _simple_frontmatter(text)
        assert fm.get("name"), f"{path}: missing name in frontmatter"
        assert fm.get("description"), f"{path}: missing description in frontmatter"
        assert body.strip(), f"{path}: empty body"


def test_commands_reference_existing_skills():
    for path in (REPO / "commands").glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in WIKI_SKILL.finditer(text):
            sid = m.group(1)
            skill_md = REPO / "skills" / sid / "SKILL.md"
            assert skill_md.is_file(), f"{path.name} references {sid} but {skill_md} missing"


def test_llm_wiki_cli_tokens_in_docs(top_level_cli: set[str]):
    roots = [REPO / "commands", REPO / "skills"]
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.md"):
            if "references" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for tok in _scan_llm_wiki_tokens(text):
                assert tok in top_level_cli, f"{path}: unknown llm-wiki subcommand {tok!r}"


def test_smoke_check_sections_in_commands_and_skills():
    for path in list((REPO / "commands").glob("*.md")) + list((REPO / "skills").glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        assert "## Smoke check" in text, f"{path.relative_to(REPO)}: missing ## Smoke check"
        lower = text.lower()
        idx = lower.find("## smoke check")
        tail = text[idx:] if idx >= 0 else ""
        assert "cli" in tail[:2000].lower(), f"{path}: smoke section should mention CLI"
        assert "prompt" in tail[:2000].lower(), f"{path}: smoke section should mention Prompt"


def test_skill_directory_matches_frontmatter_name():
    for path in sorted((REPO / "skills").glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, _ = _simple_frontmatter(text)
        name = fm.get("name", "")
        parent = path.parent.name
        assert name == parent, f"{path}: frontmatter name {name!r} != directory {parent!r}"


# Core skills that must declare when_to_use (third-person routing hint).
_WHEN_TO_USE_SKILLS = (
    "wiki-query",
    "wiki-ingest",
    "wiki-fetch",
    "wiki-research",
    "wiki-status",
    "wiki-onboard",
)

# Skills that must include a vault path preamble (LLM_WIKI_VAULT or section title).
_VAULT_PREAMBLE_SKILLS = (
    "wiki-setup",
    "wiki-status",
    "wiki-onboard",
)


def test_core_skills_have_when_to_use():
    for sid in _WHEN_TO_USE_SKILLS:
        path = REPO / "skills" / sid / "SKILL.md"
        assert path.is_file(), f"missing skill {sid}"
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, _ = _simple_frontmatter(text)
        wtu = (fm.get("when_to_use") or "").strip()
        assert wtu, f"{sid}: missing when_to_use in frontmatter"


def test_setup_status_onboard_have_vault_path_preamble():
    for sid in _VAULT_PREAMBLE_SKILLS:
        path = REPO / "skills" / sid / "SKILL.md"
        assert path.is_file(), f"missing skill {sid}"
        text = path.read_text(encoding="utf-8", errors="replace")
        assert "LLM_WIKI_VAULT" in text or "Vault path preamble" in text, (
            f"{sid}: expected vault path preamble (LLM_WIKI_VAULT or 'Vault path preamble')"
        )
