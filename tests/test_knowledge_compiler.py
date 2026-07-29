"""Tests for wiki schema, lint, fact conflicts, and compile gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    v = tmp_path / "llm-wiki"
    (v / "wiki").mkdir(parents=True)
    (v / "raw").mkdir()
    (v / "outputs").mkdir()
    (v / "config.json").write_text(
        json.dumps(
            {
                "version": 1,
                "knowledge_graph": {
                    "enabled": True,
                    "backend": "json",
                    "fact_check_on_add": True,
                },
                "compile": {"schema_required": False, "fail_on_kg_conflicts": True},
                "viewer": {"enabled": False},
                "git": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )
    (v / "CLAUDE.md").write_text("# vault\n", encoding="utf-8")
    (v / "wiki" / "index.md").write_text(
        "# Index\n\n[[topic]]\n",
        encoding="utf-8",
    )
    (v / "wiki" / "topic.md").write_text(
        "---\ntitle: Topic\nupdated: 2026-07-01\nsources:\n  - raw/a.md\nconfidence: 0.9\n---\n# Topic\n\nSee [[index]].\n",
        encoding="utf-8",
    )
    (v / "raw" / "a.md").write_text("# a\n", encoding="utf-8")
    return v


def test_schema_parse_and_validate(vault: Path) -> None:
    from lib.wiki_schema import parse_wiki_frontmatter, validate_page_schema

    text = (vault / "wiki" / "topic.md").read_text(encoding="utf-8")
    fm, body = parse_wiki_frontmatter(text)
    assert fm.get("title") == "Topic"
    assert "raw/a.md" in fm.get("sources", [])
    assert "Topic" in body
    assert validate_page_schema(vault / "wiki" / "topic.md", text, require_sources=True) == []


def test_schema_requires_sources(vault: Path) -> None:
    from lib.wiki_schema import validate_page_schema

    p = vault / "wiki" / "bare.md"
    p.write_text("# Bare\n", encoding="utf-8")
    issues = validate_page_schema(p, p.read_text(encoding="utf-8"), require_sources=True)
    assert any("sources" in i for i in issues)


def test_lint_report(vault: Path) -> None:
    from lib.config_loader import load_config
    from lib.wiki_lint import lint_vault

    cfg = load_config(vault)
    report = lint_vault(vault, cfg, check_schema=False)
    assert "issues" in report
    assert "ok" in report


def test_fact_conflicts() -> None:
    from lib.fact_checker import find_predicate_conflicts

    triples = [
        {"s": "Auth", "p": "uses", "o": "OAuth", "valid_until": None},
        {"s": "Auth", "p": "uses", "o": "SAML", "valid_until": None},
        {"s": "Auth", "p": "uses", "o": "OAuth", "valid_until": "2020-01-01"},
    ]
    conflicts = find_predicate_conflicts(triples)
    assert len(conflicts) == 1
    assert set(conflicts[0]["objects"]) == {"OAuth", "SAML"}


def test_kg_add_fact_check(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import cli.ops_commands as oc

    class Args:
        vault = str(vault)
        kg_sub = "add"
        subject = "Auth"
        predicate = "uses"
        object = "OAuth"
        valid_from = None
        source = None

    assert oc.cmd_kg(Args()) == 0

    class Args2:
        vault = str(vault)
        kg_sub = "add"
        subject = "Auth"
        predicate = "uses"
        object = "SAML"
        valid_from = None
        source = None

    assert oc.cmd_kg(Args2()) == 1


def test_compile_pipeline(vault: Path) -> None:
    from lib.compile_pipeline import run_compile
    from lib.config_loader import load_config

    cfg = load_config(vault)
    result = run_compile(vault, cfg, skip_site=True, json_out=False)
    assert result["exit_code"] == 0
    assert result["ok"] is True


def test_knowledge_tests(vault: Path) -> None:
    from lib.knowledge_tests import run_knowledge_tests

    tests = [
        {"id": "topic", "path": "topic.md", "contains": ["Topic"], "absent": ["ZZZNOPE"]},
    ]
    report = run_knowledge_tests(vault, tests)
    assert report["ok"] is True
    assert report["failed"] == 0


def test_multi_valued_predicates_ignored() -> None:
    from lib.fact_checker import find_predicate_conflicts

    triples = [
        {"s": "Auth", "p": "mentions", "o": "A"},
        {"s": "Auth", "p": "mentions", "o": "B"},
    ]
    assert find_predicate_conflicts(triples) == []


def test_entity_aliases_merge(vault: Path) -> None:
    from lib.config_loader import load_config, save_config
    from lib.knowledge_graph import get_kg_backend

    cfg = load_config(vault)
    cfg.setdefault("knowledge_graph", {})["aliases"] = {"OAuth2": "OAuth"}
    save_config(vault, cfg)
    cfg = load_config(vault)
    kg = get_kg_backend(vault, cfg)
    tid1 = kg.add_triple("Auth", "uses", "OAuth2")
    tid2 = kg.add_triple("Auth", "uses", "OAuth")
    assert tid1 == tid2
    rows = kg.query_entity("OAuth2")
    assert any(r.get("o") == "OAuth" for r in rows)
    assert any(r.get("s") == "Auth" for r in rows)


def test_ontology_rejects_unknown_predicate(vault: Path) -> None:
    from lib.config_loader import load_config, save_config
    from lib.knowledge_graph import get_kg_backend

    cfg = load_config(vault)
    kg_cfg = cfg.setdefault("knowledge_graph", {})
    kg_cfg["allowed_predicates"] = ["uses"]
    kg_cfg["ontology_strict"] = True
    save_config(vault, cfg)
    cfg = load_config(vault)
    kg = get_kg_backend(vault, cfg)
    kg.add_triple("Auth", "uses", "OAuth")
    try:
        kg.add_triple("Auth", "invented_rel", "X")
        raise AssertionError("expected ontology ValueError")
    except ValueError as exc:
        assert "allowed_predicates" in str(exc)


def test_claims_and_incremental_compile(vault: Path) -> None:
    from lib.claims import extract_vault_claims, pages_citing_raw
    from lib.compile_pipeline import run_compile
    from lib.config_loader import load_config

    (vault / "wiki" / "topic.md").write_text(
        "---\ntitle: Topic\nupdated: 2026-07-01\nsources:\n  - raw/a.md\nconfidence: 0.9\n---\n"
        "# Topic\n\n- OAuth is preferred source: `raw/a.md`\n",
        encoding="utf-8",
    )
    (vault / "wiki" / "other.md").write_text(
        "---\ntitle: Other\nupdated: 2026-07-01\nsources:\n  - raw/b.md\n---\n# Other\n",
        encoding="utf-8",
    )
    (vault / "raw" / "b.md").write_text("# b\n", encoding="utf-8")
    (vault / "wiki" / "index.md").write_text("# Index\n\n[[topic]]\n[[other]]\n", encoding="utf-8")

    assert pages_citing_raw(vault, "raw/a.md") == ["topic.md"]
    claims = extract_vault_claims(vault)
    assert any("OAuth" in c["text"] for c in claims)

    cfg = load_config(vault)
    result = run_compile(vault, cfg, skip_site=True, skip_kg=True, raw_path="raw/a.md")
    assert result["exit_code"] == 0
    scope = next(s for s in result["steps"] if s.get("step") == "scope")
    assert scope["pages"] == ["topic.md"]
    assert (vault / "outputs" / "claims.json").is_file()
