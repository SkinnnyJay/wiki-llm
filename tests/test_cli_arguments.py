"""Typed boundary tests for argparse-backed CLI command inputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from cli.arguments import (
    BenchmarkArgs,
    BuildSiteArgs,
    CompileArgs,
    ConfigureArgs,
    DiffArgs,
    GitArgs,
    GraphArgs,
    IngestArgs,
    IntegrationsArgs,
    KnowledgeGraphArgs,
    KnowledgeTestArgs,
    LintArgs,
    MemoryArgs,
    MetricsArgs,
    RawFinishArgs,
    RawRecordArgs,
    RawValidateArgs,
    ResearchLoopArgs,
    SearchArgs,
    SecurityArgs,
    SetupArgs,
    TeardownArgs,
    ValidateArgs,
    VaultArgs,
    WakeupArgs,
    boolean,
    nonnegative_int,
    port_number,
)
from cli.parser import build_parser


def test_configure_args_decodes_optional_strings_and_boolean_flags() -> None:
    args = argparse.Namespace(
        vault="/tmp/wiki",
        wiki_root="wiki",
        og_base_url="https://example.test/wiki",
        viewer_enabled=True,
        git_enabled=False,
        research_enabled=None,
        security_enabled=None,
        persona_name="Curator",
    )

    config = ConfigureArgs.from_namespace(args)

    assert config.vault == "/tmp/wiki"
    assert config.wiki_root == "wiki"
    assert config.og_base_url == "https://example.test/wiki"
    assert config.viewer_enabled is True
    assert config.git_enabled is False
    assert config.research_enabled is None
    assert config.security_enabled is None
    assert config.persona_name == "Curator"


def test_configure_args_rejects_invalid_namespace_field_types() -> None:
    args = argparse.Namespace(
        vault=None,
        wiki_root=None,
        og_base_url=None,
        viewer_enabled="true",
        git_enabled=None,
        research_enabled=None,
        security_enabled=None,
        persona_name=None,
    )

    with pytest.raises(ValueError, match="viewer_enabled"):
        ConfigureArgs.from_namespace(args)


def test_search_args_accepts_the_documented_search_contract() -> None:
    args = argparse.Namespace(
        vault="/tmp/wiki",
        query="workflow approvals",
        limit=10,
        tag="security",
        scope="wiki",
    )

    search = SearchArgs.from_namespace(args)

    assert search.vault == "/tmp/wiki"
    assert search.query == "workflow approvals"
    assert search.limit == 10
    assert search.tag == "security"
    assert search.scope == "wiki"


def test_setup_teardown_and_graph_args_decode_their_parser_contracts() -> None:
    setup = SetupArgs.from_namespace(
        argparse.Namespace(root=".", vault=None, interactive=False, defaults=True)
    )
    teardown = TeardownArgs.from_namespace(
        argparse.Namespace(vault=None, dry_run=True, purge=False, artifacts=True, yes=True)
    )
    graph = GraphArgs.from_namespace(
        argparse.Namespace(vault="/tmp/wiki", out=Path("graph"), mode="links")
    )

    assert setup.defaults is True
    assert teardown.artifacts is True
    assert graph.out == Path("graph")
    assert graph.mode == "links"


def test_graph_args_override_alias_mode_without_mutating_namespace() -> None:
    args = argparse.Namespace(vault=None, out=None)

    graph = GraphArgs.from_namespace(args, mode_override="knowledge")

    assert graph.mode == "knowledge"


def test_build_site_args_decode_viewer_lifecycle_contract() -> None:
    options = BuildSiteArgs.from_namespace(
        argparse.Namespace(
            vault="/tmp/wiki",
            if_stale=True,
            serve=False,
            serve_background=True,
            open=True,
            port=8765,
            stop_serving=False,
        )
    )

    assert options.serve_background is True
    assert options.open_browser is True
    assert options.port == 8765


def test_knowledge_graph_args_decode_all_typed_command_values() -> None:
    options = KnowledgeGraphArgs.from_namespace(
        argparse.Namespace(
            vault="/tmp/wiki",
            kg_sub="add",
            subject="Project",
            predicate="depends_on",
            object="Database",
            valid_from="2026-01-01",
            source="wiki/project.md",
            entity=None,
            as_of=None,
            ended=None,
            json_out=False,
        )
    )

    assert options.command == "add"
    assert options.object_value == "Database"


def test_memory_args_decode_session_memory_contract() -> None:
    options = MemoryArgs.from_namespace(
        argparse.Namespace(
            vault=None,
            memory_sub="save",
            session_id="session-1",
            current=False,
            summary="Summary",
            compact_summary=None,
            tags="research,security",
            metadata='{"source":"test"}',
            message_preview=None,
            message_preview_file=None,
            session_filter=None,
            tag=None,
            json_out=False,
            session_id_arg=None,
            query=None,
            limit=None,
            older_than=None,
            keep=None,
            dry_run=False,
        )
    )

    assert options.command == "save"
    assert options.session_id == "session-1"


def test_metrics_args_decode_record_contract() -> None:
    options = MetricsArgs.from_namespace(
        argparse.Namespace(
            vault=None,
            metrics_sub="record",
            key="search.query_ms",
            value="12.5",
            meta='{"backend":"fts5"}',
            tags="search",
            since=None,
            limit=None,
            metrics_json=False,
            before=None,
            yes=False,
            metrics_report_since=None,
            metrics_report_key=None,
            metrics_report_out=None,
            metrics_summary_since=None,
            metrics_summary_key=None,
            metrics_summary_json=False,
        )
    )

    assert options.command == "record"
    assert options.key == "search.query_ms"


def test_benchmark_args_decode_run_contract() -> None:
    options = BenchmarkArgs.from_namespace(
        argparse.Namespace(
            vault=None,
            benchmark_sub="run",
            benchmark_suite="lme",
            benchmark_backend="fts5",
            benchmark_compress="raw",
            benchmark_limit=10,
            benchmark_top_k=5,
            benchmark_data=None,
            benchmark_no_metrics=False,
            benchmark_peer=["mem0"],
            benchmark_strict_peers=True,
            benchmark_since=None,
            benchmark_json=False,
            benchmark_history_limit=None,
            benchmark_compare_a=None,
            benchmark_compare_b=None,
            benchmark_analyze_suite=None,
            benchmark_failures_path=None,
            benchmark_analyze_json=False,
        )
    )

    assert options.command == "run"
    assert options.peers == ["mem0"]
    assert options.strict_peers is True


def test_ingest_args_decode_adapter_passthrough_contract() -> None:
    options = IngestArgs.from_namespace(
        argparse.Namespace(
            vault="/tmp/wiki",
            list=False,
            force=True,
            force_security=False,
            tags="security, research",
            adapter_args=["url", "https://example.test"],
        )
    )

    assert options.adapter_args == ["url", "https://example.test"]
    assert options.force is True


def test_integrations_args_decode_key_write_contract() -> None:
    options = IntegrationsArgs.from_namespace(
        argparse.Namespace(
            vault=None,
            integrations_cmd="set-key",
            adapter="brave",
            key_value="secret",
        )
    )

    assert options.command == "set-key"
    assert options.adapter == "brave"


def test_raw_lifecycle_args_decode_safe_defaults() -> None:
    validate = RawValidateArgs.from_namespace(
        argparse.Namespace(vault=None, path="notes/item.md", autofix=True)
    )
    finish = RawFinishArgs.from_namespace(
        argparse.Namespace(
            vault=None,
            path="notes/item.md",
            message="prepare note",
            goal=None,
            record_action=None,
            notes=None,
            autofix=None,
            skip_git=True,
        )
    )
    record = RawRecordArgs.from_namespace(
        argparse.Namespace(
            vault=None,
            path="notes/item.md",
            goal="prepared",
            action="validated",
            notes=None,
        )
    )

    assert validate.autofix is True
    assert finish.autofix is True
    assert finish.skip_git is True
    assert record.action == "validated"


def test_git_args_decode_lifecycle_contract() -> None:
    options = GitArgs.from_namespace(
        argparse.Namespace(
            vault=None,
            git_cmd="lifecycle",
            n=50,
            since="2026-01-01",
            grep=None,
            staged=False,
            message=None,
            phase="prepare",
            lifecycle_json=True,
        )
    )

    assert options.command == "lifecycle"
    assert options.count == 50
    assert options.lifecycle_json is True


def test_quality_gate_args_decode_distinct_command_contracts() -> None:
    validate = ValidateArgs.from_namespace(
        argparse.Namespace(vault=None, wikilinks=True, schema=False)
    )
    lint = LintArgs.from_namespace(
        argparse.Namespace(
            vault=None,
            schema=True,
            no_stale=False,
            no_outputs=True,
            json_out=False,
            write_report=True,
        )
    )
    diff = DiffArgs.from_namespace(
        argparse.Namespace(vault=None, since="HEAD~2", json_out=True, write_report=False)
    )
    compile_args = CompileArgs.from_namespace(
        argparse.Namespace(
            vault=None,
            schema=False,
            no_kg=True,
            no_site=False,
            raw="raw/notes.md",
            stubs=False,
            json_out=True,
        )
    )
    knowledge_test = KnowledgeTestArgs.from_namespace(
        argparse.Namespace(vault=None, file="checks.json", json_out=False)
    )

    assert validate.wikilinks is True
    assert lint.write_report is True
    assert diff.since == "HEAD~2"
    assert compile_args.raw == "raw/notes.md"
    assert knowledge_test.file == "checks.json"


def test_simple_operational_args_decode_their_contracts() -> None:
    research = ResearchLoopArgs.from_namespace(
        argparse.Namespace(vault=None, task="topic-1", dry_run=True, force=False)
    )
    security = SecurityArgs.from_namespace(argparse.Namespace(file="raw/note.md"))
    wakeup = WakeupArgs.from_namespace(
        argparse.Namespace(vault="/tmp/wiki", update_claude=True)
    )
    vault = VaultArgs.from_namespace(argparse.Namespace(vault="/tmp/wiki"))

    assert research.task == "topic-1"
    assert security.file == "raw/note.md"
    assert wakeup.update_claude is True
    assert vault.vault == "/tmp/wiki"


@pytest.mark.parametrize("limit", [0, -1])
def test_search_args_rejects_unbounded_or_empty_limits(limit: int) -> None:
    args = argparse.Namespace(
        vault=None,
        query="workflow",
        limit=limit,
        tag="",
        scope="all",
    )

    with pytest.raises(ValueError, match="limit"):
        SearchArgs.from_namespace(args)


@pytest.mark.parametrize("limit", ["0", "-1"])
def test_search_parser_rejects_non_positive_limits(limit: str) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["search", "workflow", "--limit", limit])

    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    ("value", "expected"),
    [("true", True), ("YES", True), ("0", False), ("off", False)],
)
def test_boolean_accepts_explicit_boolean_spellings(value: str, expected: bool) -> None:
    assert boolean(value) is expected


@pytest.mark.parametrize("value", ["", "maybe", "2"])
def test_boolean_rejects_ambiguous_values(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        boolean(value)


@pytest.mark.parametrize("value", ["0", "65536", "-1"])
def test_port_number_rejects_out_of_range_ports(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        port_number(value)


def test_nonnegative_int_keeps_zero_for_commands_that_define_it_as_all() -> None:
    assert nonnegative_int("0") == 0


@pytest.mark.parametrize(
    "command",
    [
        ["configure", "--viewer-enabled", "maybe"],
        ["build-site", "--port", "0"],
        ["mcp", "--port", "70000"],
        ["metrics", "query", "--limit", "0"],
        ["benchmark", "run", "--limit", "-1"],
        ["benchmark", "history", "--limit", "0"],
        ["memory", "recall", "query", "--limit", "-1"],
    ],
)
def test_parser_rejects_invalid_scalar_contracts(command: list[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(command)

    assert exc_info.value.code == 2
