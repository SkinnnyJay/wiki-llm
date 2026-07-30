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


def test_empty_raw_scope_does_not_full_vault_lint(vault: Path) -> None:
    from lib.compile_pipeline import run_compile
    from lib.config_loader import load_config
    from lib.wiki_lint import lint_vault

    (vault / "wiki" / "orphan.md").write_text("# Orphan\n", encoding="utf-8")
    cfg = load_config(vault)
    # Full vault would flag orphan; empty surgical scope must not.
    full = lint_vault(vault, cfg, check_schema=False)
    assert any(i["code"] == "orphan" for i in full["issues"])

    result = run_compile(
        vault, cfg, skip_site=True, skip_kg=True, raw_path="raw/does-not-exist.md"
    )
    assert result["exit_code"] == 0
    scope = next(s for s in result["steps"] if s.get("step") == "scope")
    assert scope["page_count"] == 0
    lint_step = next(s for s in result["steps"] if s.get("step") == "lint")
    assert lint_step["ok"] is True
    assert lint_step["only_pages"] == []


def test_raw_path_rejects_traversal(vault: Path) -> None:
    from lib.claims import normalize_raw_rel
    from lib.compile_pipeline import run_compile
    from lib.config_loader import load_config

    try:
        normalize_raw_rel("../etc/passwd")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass

    cfg = load_config(vault)
    result = run_compile(vault, cfg, skip_site=True, skip_kg=True, raw_path="../../x")
    assert result["exit_code"] == 1
    assert any(s.get("step") == "scope" and not s.get("ok") for s in result["steps"])


def test_compile_stubs_write_outputs_only(vault: Path) -> None:
    from lib.compile_pipeline import run_compile
    from lib.config_loader import load_config

    (vault / "wiki" / "topic.md").write_text(
        "---\ntitle: Topic\nsources:\n  - raw/a.md\n---\n# Topic\n\n- Fact source: `raw/a.md`\n",
        encoding="utf-8",
    )
    before = {p.name for p in (vault / "wiki").rglob("*.md")}
    cfg = load_config(vault)
    result = run_compile(vault, cfg, skip_site=True, skip_kg=True, write_stubs=True)
    assert result["exit_code"] == 0
    stubs = list((vault / "outputs" / "stubs").glob("*.md"))
    assert stubs
    assert {p.name for p in (vault / "wiki").rglob("*.md")} == before
    assert all("review_required: true" in p.read_text(encoding="utf-8") for p in stubs)


def test_compile_fails_on_kg_conflicts(vault: Path) -> None:
    from lib.compile_pipeline import run_compile
    from lib.config_loader import load_config
    from lib.knowledge_graph import get_kg_backend

    cfg = load_config(vault)
    cfg.setdefault("compile", {})["fail_on_kg_conflicts"] = True
    kg = get_kg_backend(vault, cfg)
    kg.add_triple("Auth", "uses", "OAuth")
    # Bypass fact_check path by writing second object via invalidate-off: use backend directly
    # after disabling fact check for second add through JSON file
    data = json.loads((vault / ".kg.json").read_text(encoding="utf-8"))
    data["triples"].append(
        {
            "id": "deadbeefcafe",
            "s": "Auth",
            "p": "uses",
            "o": "SAML",
            "valid_from": "2026-01-01",
        }
    )
    (vault / ".kg.json").write_text(json.dumps(data), encoding="utf-8")
    result = run_compile(vault, cfg, skip_site=True, skip_kg=False)
    # rebuild may add more triples but conflict Auth/uses remains
    kg_step = next(s for s in result["steps"] if s.get("step") == "kg")
    assert kg_step.get("conflicts", 0) >= 1
    assert result["exit_code"] == 1


def test_ontology_strict_keeps_structural_predicates(vault: Path) -> None:
    from lib.config_loader import load_config, save_config
    from lib.kg_ontology import predicate_allowed

    cfg = load_config(vault)
    kg_cfg = cfg.setdefault("knowledge_graph", {})
    kg_cfg["allowed_predicates"] = ["uses"]
    kg_cfg["ontology_strict"] = True
    save_config(vault, cfg)
    cfg = load_config(vault)
    assert predicate_allowed("uses", cfg)
    assert predicate_allowed("mentions", cfg)
    assert predicate_allowed("links_to", cfg)
    assert not predicate_allowed("invented_rel", cfg)


def test_mcp_compile_gated_by_default(vault: Path) -> None:
    from mcp.registry import build_active_tools
    from mcp.tools_registry import READ_ONLY_TOOL_NAMES, TOOLS

    cfg = {"mcp": {"enabled": True, "tools_mode": "full", "compile_enabled": False}}
    active = build_active_tools(cfg, TOOLS, READ_ONLY_TOOL_NAMES)
    assert "wiki_compile" not in active
    assert "wiki_lint" not in active
    assert "wiki_knowledge_test" in active

    cfg["mcp"]["compile_enabled"] = True
    active2 = build_active_tools(cfg, TOOLS, READ_ONLY_TOOL_NAMES)
    assert "wiki_compile" in active2
    assert "wiki_lint" in active2
