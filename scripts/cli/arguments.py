"""Validated value objects for argparse command boundaries.

``argparse.Namespace`` exposes every attribute as ``Any``. Command-specific
value objects make the small, stable argument contracts explicit before values
reach domain code.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

SearchScope = Literal["all", "wiki", "raw", "memory"]
SEARCH_SCOPES: tuple[SearchScope, ...] = ("all", "wiki", "raw", "memory")
GraphMode = Literal["links", "knowledge"]
GRAPH_MODES: tuple[GraphMode, ...] = ("links", "knowledge")
KnowledgeGraphCommand = Literal[
    "add",
    "query",
    "invalidate",
    "timeline",
    "stats",
    "rebuild",
    "conflicts",
]
KNOWLEDGE_GRAPH_COMMANDS: tuple[KnowledgeGraphCommand, ...] = (
    "add",
    "query",
    "invalidate",
    "timeline",
    "stats",
    "rebuild",
    "conflicts",
)
MemoryCommand = Literal["save", "log", "list", "show", "recall", "prune"]
MEMORY_COMMANDS: tuple[MemoryCommand, ...] = ("save", "log", "list", "show", "recall", "prune")
MetricsCommand = Literal["record", "query", "stats", "clear", "report", "summary"]
METRICS_COMMANDS: tuple[MetricsCommand, ...] = (
    "record",
    "query",
    "stats",
    "clear",
    "report",
    "summary",
)
BenchmarkCommand = Literal["run", "suites", "report", "history", "compare", "analyze"]
BENCHMARK_COMMANDS: tuple[BenchmarkCommand, ...] = (
    "run",
    "suites",
    "report",
    "history",
    "compare",
    "analyze",
)
IntegrationsCommand = Literal["status", "validate", "wizard", "set-key"]
INTEGRATIONS_COMMANDS: tuple[IntegrationsCommand, ...] = (
    "status",
    "validate",
    "wizard",
    "set-key",
)
RawAction = Literal["validated", "autofixed", "llm_cleaned", "noted"]
RAW_ACTIONS: tuple[RawAction, ...] = ("validated", "autofixed", "llm_cleaned", "noted")
GitCommand = Literal["init", "status", "log", "diff", "snapshot", "query", "lifecycle"]
GIT_COMMANDS: tuple[GitCommand, ...] = (
    "init",
    "status",
    "log",
    "diff",
    "snapshot",
    "query",
    "lifecycle",
)


def _optional_text(args: argparse.Namespace, name: str) -> str | None:
    value = getattr(args, name, None)
    if value is None or isinstance(value, str):
        return value
    raise ValueError(f"{name} must be a string or None")


def _optional_bool(args: argparse.Namespace, name: str) -> bool | None:
    value = getattr(args, name, None)
    if value is None or isinstance(value, bool):
        return value
    raise ValueError(f"{name} must be a boolean or None")


def _required_text(args: argparse.Namespace, name: str) -> str:
    value = getattr(args, name, None)
    if isinstance(value, str) and value.strip():
        return value
    raise ValueError(f"{name} must be a non-empty string")


def _positive_int(args: argparse.Namespace, name: str) -> int:
    value = getattr(args, name, None)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    raise ValueError(f"{name} must be a positive integer")


def _required_bool(args: argparse.Namespace, name: str) -> bool:
    value = getattr(args, name, None)
    if isinstance(value, bool):
        return value
    raise ValueError(f"{name} must be a boolean")


def _optional_path(args: argparse.Namespace, name: str) -> Path | None:
    value = getattr(args, name, None)
    if value is None or isinstance(value, Path):
        return value
    raise ValueError(f"{name} must be a Path or None")


def _optional_int(args: argparse.Namespace, name: str) -> int | None:
    value = getattr(args, name, None)
    if value is None or (isinstance(value, int) and not isinstance(value, bool)):
        return value
    raise ValueError(f"{name} must be an integer or None")


def _optional_text_list(args: argparse.Namespace, name: str) -> list[str] | None:
    value = getattr(args, name, None)
    if value is None:
        return None
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ValueError(f"{name} must be a list of strings or None")


def required_text(value: str | None, name: str) -> str:
    """Return a non-blank command value after a command-specific decode."""
    if value and value.strip():
        return value
    raise ValueError(f"{name} must be a non-empty string")


def positive_int(value: str) -> int:
    """Argparse converter for bounded result limits and similar quantities."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def nonnegative_int(value: str) -> int:
    """Argparse converter for quantities where zero has an explicit meaning."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def port_number(value: str) -> int:
    """Argparse converter for valid TCP/UDP port numbers."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a port number from 1 to 65535") from exc
    if not 1 <= parsed <= 65535:
        raise argparse.ArgumentTypeError("must be a port number from 1 to 65535")
    return parsed


def boolean(value: str) -> bool:
    """Argparse converter that rejects ambiguous boolean spelling."""
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError("must be true or false")


@dataclass(frozen=True)
class SetupArgs:
    root: str
    vault: str | None
    interactive: bool
    defaults: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> SetupArgs:
        return cls(
            root=_required_text(args, "root"),
            vault=_optional_text(args, "vault"),
            interactive=_required_bool(args, "interactive"),
            defaults=_required_bool(args, "defaults"),
        )


@dataclass(frozen=True)
class TeardownArgs:
    vault: str | None
    dry_run: bool
    purge: bool
    artifacts: bool
    yes: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> TeardownArgs:
        return cls(
            vault=_optional_text(args, "vault"),
            dry_run=_required_bool(args, "dry_run"),
            purge=_required_bool(args, "purge"),
            artifacts=_required_bool(args, "artifacts"),
            yes=_required_bool(args, "yes"),
        )


@dataclass(frozen=True)
class GraphArgs:
    vault: str | None
    out: Path | None
    mode: GraphMode

    @classmethod
    def from_namespace(
        cls,
        args: argparse.Namespace,
        *,
        mode_override: GraphMode | None = None,
    ) -> GraphArgs:
        mode = mode_override or _required_text(args, "mode")
        if mode not in GRAPH_MODES:
            raise ValueError(f"mode must be one of: {', '.join(GRAPH_MODES)}")
        return cls(
            vault=_optional_text(args, "vault"),
            out=_optional_path(args, "out"),
            mode=cast(GraphMode, mode),
        )


@dataclass(frozen=True)
class BuildSiteArgs:
    vault: str | None
    if_stale: bool
    serve: bool
    serve_background: bool
    open_browser: bool
    port: int | None
    stop_serving: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> BuildSiteArgs:
        return cls(
            vault=_optional_text(args, "vault"),
            if_stale=_required_bool(args, "if_stale"),
            serve=_required_bool(args, "serve"),
            serve_background=_required_bool(args, "serve_background"),
            open_browser=_required_bool(args, "open"),
            port=_optional_int(args, "port"),
            stop_serving=_required_bool(args, "stop_serving"),
        )


@dataclass(frozen=True)
class KnowledgeGraphArgs:
    vault: str | None
    command: KnowledgeGraphCommand
    subject: str | None
    predicate: str | None
    object_value: str | None
    valid_from: str | None
    source: str | None
    entity: str | None
    as_of: str | None
    ended: str | None
    json_out: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> KnowledgeGraphArgs:
        command = _required_text(args, "kg_sub")
        if command not in KNOWLEDGE_GRAPH_COMMANDS:
            raise ValueError(
                f"kg_sub must be one of: {', '.join(KNOWLEDGE_GRAPH_COMMANDS)}"
            )
        return cls(
            vault=_optional_text(args, "vault"),
            command=cast(KnowledgeGraphCommand, command),
            subject=_optional_text(args, "subject"),
            predicate=_optional_text(args, "predicate"),
            object_value=_optional_text(args, "object"),
            valid_from=_optional_text(args, "valid_from"),
            source=_optional_text(args, "source"),
            entity=_optional_text(args, "entity"),
            as_of=_optional_text(args, "as_of"),
            ended=_optional_text(args, "ended"),
            json_out=_optional_bool(args, "json_out") or False,
        )


@dataclass(frozen=True)
class MemoryArgs:
    vault: str | None
    command: MemoryCommand
    session_id: str | None
    current: bool
    summary: str | None
    compact_summary: str | None
    tags: str | None
    metadata: str | None
    message_preview: str | None
    message_preview_file: str | None
    session_filter: str | None
    tag: str | None
    json_out: bool
    session_id_arg: str | None
    query: str | None
    limit: int | None
    older_than: int | None
    keep: int | None
    dry_run: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> MemoryArgs:
        command = _required_text(args, "memory_sub")
        if command not in MEMORY_COMMANDS:
            raise ValueError(f"memory_sub must be one of: {', '.join(MEMORY_COMMANDS)}")
        return cls(
            vault=_optional_text(args, "vault"),
            command=cast(MemoryCommand, command),
            session_id=_optional_text(args, "session_id"),
            current=_optional_bool(args, "current") or False,
            summary=_optional_text(args, "summary"),
            compact_summary=_optional_text(args, "compact_summary"),
            tags=_optional_text(args, "tags"),
            metadata=_optional_text(args, "metadata"),
            message_preview=_optional_text(args, "message_preview"),
            message_preview_file=_optional_text(args, "message_preview_file"),
            session_filter=_optional_text(args, "session_filter"),
            tag=_optional_text(args, "tag"),
            json_out=_optional_bool(args, "json_out") or False,
            session_id_arg=_optional_text(args, "session_id_arg"),
            query=_optional_text(args, "query"),
            limit=_optional_int(args, "limit"),
            older_than=_optional_int(args, "older_than"),
            keep=_optional_int(args, "keep"),
            dry_run=_optional_bool(args, "dry_run") or False,
        )


@dataclass(frozen=True)
class MetricsArgs:
    vault: str | None
    command: MetricsCommand
    key: str | None
    value: str | None
    meta: str | None
    tags: str | None
    since: str | None
    limit: int | None
    json_out: bool
    before: str | None
    yes: bool
    report_since: str | None
    report_key: str | None
    report_out: str | None
    summary_since: str | None
    summary_key: str | None
    summary_json: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> MetricsArgs:
        command = _required_text(args, "metrics_sub")
        if command not in METRICS_COMMANDS:
            raise ValueError(f"metrics_sub must be one of: {', '.join(METRICS_COMMANDS)}")
        return cls(
            vault=_optional_text(args, "vault"),
            command=cast(MetricsCommand, command),
            key=_optional_text(args, "key"),
            value=_optional_text(args, "value"),
            meta=_optional_text(args, "meta"),
            tags=_optional_text(args, "tags"),
            since=_optional_text(args, "since"),
            limit=_optional_int(args, "limit"),
            json_out=_optional_bool(args, "metrics_json") or False,
            before=_optional_text(args, "before"),
            yes=_optional_bool(args, "yes") or False,
            report_since=_optional_text(args, "metrics_report_since"),
            report_key=_optional_text(args, "metrics_report_key"),
            report_out=_optional_text(args, "metrics_report_out"),
            summary_since=_optional_text(args, "metrics_summary_since"),
            summary_key=_optional_text(args, "metrics_summary_key"),
            summary_json=_optional_bool(args, "metrics_summary_json") or False,
        )


@dataclass(frozen=True)
class BenchmarkArgs:
    vault: str | None
    command: BenchmarkCommand
    suite: str | None
    backend: str | None
    compress: str | None
    limit: int | None
    top_k: int | None
    data: str | None
    no_metrics: bool
    peers: list[str] | None
    strict_peers: bool
    since: str | None
    json_out: bool
    history_limit: int | None
    compare_a: int | None
    compare_b: int | None
    analyze_suite: str | None
    failures_path: str | None
    analyze_json: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> BenchmarkArgs:
        command = _required_text(args, "benchmark_sub")
        if command not in BENCHMARK_COMMANDS:
            raise ValueError(f"benchmark_sub must be one of: {', '.join(BENCHMARK_COMMANDS)}")
        return cls(
            vault=_optional_text(args, "vault"),
            command=cast(BenchmarkCommand, command),
            suite=_optional_text(args, "benchmark_suite"),
            backend=_optional_text(args, "benchmark_backend"),
            compress=_optional_text(args, "benchmark_compress"),
            limit=_optional_int(args, "benchmark_limit"),
            top_k=_optional_int(args, "benchmark_top_k"),
            data=_optional_text(args, "benchmark_data"),
            no_metrics=_optional_bool(args, "benchmark_no_metrics") or False,
            peers=_optional_text_list(args, "benchmark_peer"),
            strict_peers=_optional_bool(args, "benchmark_strict_peers") or False,
            since=_optional_text(args, "benchmark_since"),
            json_out=_optional_bool(args, "benchmark_json") or False,
            history_limit=_optional_int(args, "benchmark_history_limit"),
            compare_a=_optional_int(args, "benchmark_compare_a"),
            compare_b=_optional_int(args, "benchmark_compare_b"),
            analyze_suite=_optional_text(args, "benchmark_analyze_suite"),
            failures_path=_optional_text(args, "benchmark_failures_path"),
            analyze_json=_optional_bool(args, "benchmark_analyze_json") or False,
        )


@dataclass(frozen=True)
class IngestArgs:
    vault: str | None
    list_adapters: bool
    force: bool
    force_security: bool
    tags: str
    adapter_args: list[str]

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> IngestArgs:
        raw_tags = _optional_text(args, "tags")
        adapter_args = _optional_text_list(args, "adapter_args")
        return cls(
            vault=_optional_text(args, "vault"),
            list_adapters=_optional_bool(args, "list") or False,
            force=_optional_bool(args, "force") or False,
            force_security=_optional_bool(args, "force_security") or False,
            tags=raw_tags or "",
            adapter_args=adapter_args or [],
        )


@dataclass(frozen=True)
class IntegrationsArgs:
    vault: str | None
    command: IntegrationsCommand
    adapter: str | None
    key_value: str | None

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> IntegrationsArgs:
        command = _required_text(args, "integrations_cmd")
        if command not in INTEGRATIONS_COMMANDS:
            raise ValueError(
                f"integrations_cmd must be one of: {', '.join(INTEGRATIONS_COMMANDS)}"
            )
        return cls(
            vault=_optional_text(args, "vault"),
            command=cast(IntegrationsCommand, command),
            adapter=_optional_text(args, "adapter"),
            key_value=_optional_text(args, "key_value"),
        )


def _optional_raw_action(args: argparse.Namespace, name: str) -> RawAction | None:
    action = _optional_text(args, name)
    if action is None:
        return None
    if action not in RAW_ACTIONS:
        raise ValueError(f"{name} must be one of: {', '.join(RAW_ACTIONS)}")
    return cast(RawAction, action)


@dataclass(frozen=True)
class RawValidateArgs:
    vault: str | None
    path: str
    autofix: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> RawValidateArgs:
        return cls(
            vault=_optional_text(args, "vault"),
            path=_required_text(args, "path"),
            autofix=_optional_bool(args, "autofix") or False,
        )


@dataclass(frozen=True)
class RawFinishArgs:
    vault: str | None
    path: str
    message: str
    goal: str | None
    record_action: RawAction | None
    notes: str | None
    autofix: bool
    skip_git: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> RawFinishArgs:
        autofix = _optional_bool(args, "autofix")
        return cls(
            vault=_optional_text(args, "vault"),
            path=_required_text(args, "path"),
            message=_required_text(args, "message"),
            goal=_optional_text(args, "goal"),
            record_action=_optional_raw_action(args, "record_action"),
            notes=_optional_text(args, "notes"),
            autofix=True if autofix is None else autofix,
            skip_git=_optional_bool(args, "skip_git") or False,
        )


@dataclass(frozen=True)
class RawRecordArgs:
    vault: str | None
    path: str
    goal: str
    action: RawAction
    notes: str | None

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> RawRecordArgs:
        action = _optional_raw_action(args, "action")
        if action is None:
            raise ValueError("action must be provided")
        return cls(
            vault=_optional_text(args, "vault"),
            path=_required_text(args, "path"),
            goal=_required_text(args, "goal"),
            action=action,
            notes=_optional_text(args, "notes"),
        )


@dataclass(frozen=True)
class GitArgs:
    vault: str | None
    command: GitCommand
    count: int | None
    since: str | None
    grep: str | None
    staged: bool
    message: str | None
    phase: str | None
    lifecycle_json: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> GitArgs:
        command = _required_text(args, "git_cmd")
        if command not in GIT_COMMANDS:
            raise ValueError(f"git_cmd must be one of: {', '.join(GIT_COMMANDS)}")
        return cls(
            vault=_optional_text(args, "vault"),
            command=cast(GitCommand, command),
            count=_optional_int(args, "n"),
            since=_optional_text(args, "since"),
            grep=_optional_text(args, "grep"),
            staged=_optional_bool(args, "staged") or False,
            message=_optional_text(args, "message"),
            phase=_optional_text(args, "phase"),
            lifecycle_json=_optional_bool(args, "lifecycle_json") or False,
        )


@dataclass(frozen=True)
class ValidateArgs:
    vault: str | None
    wikilinks: bool
    schema: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> ValidateArgs:
        return cls(
            vault=_optional_text(args, "vault"),
            wikilinks=_optional_bool(args, "wikilinks") or False,
            schema=_optional_bool(args, "schema") or False,
        )


@dataclass(frozen=True)
class LintArgs:
    vault: str | None
    schema: bool
    no_stale: bool
    no_outputs: bool
    json_out: bool
    write_report: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> LintArgs:
        return cls(
            vault=_optional_text(args, "vault"),
            schema=_optional_bool(args, "schema") or False,
            no_stale=_optional_bool(args, "no_stale") or False,
            no_outputs=_optional_bool(args, "no_outputs") or False,
            json_out=_optional_bool(args, "json_out") or False,
            write_report=_optional_bool(args, "write_report") or False,
        )


@dataclass(frozen=True)
class DiffArgs:
    vault: str | None
    since: str | None
    json_out: bool
    write_report: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> DiffArgs:
        return cls(
            vault=_optional_text(args, "vault"),
            since=_optional_text(args, "since"),
            json_out=_optional_bool(args, "json_out") or False,
            write_report=_optional_bool(args, "write_report") or False,
        )


@dataclass(frozen=True)
class CompileArgs:
    vault: str | None
    schema: bool
    no_kg: bool
    no_site: bool
    raw: str | None
    stubs: bool
    json_out: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> CompileArgs:
        return cls(
            vault=_optional_text(args, "vault"),
            schema=_optional_bool(args, "schema") or False,
            no_kg=_optional_bool(args, "no_kg") or False,
            no_site=_optional_bool(args, "no_site") or False,
            raw=_optional_text(args, "raw"),
            stubs=_optional_bool(args, "stubs") or False,
            json_out=_optional_bool(args, "json_out") or False,
        )


@dataclass(frozen=True)
class KnowledgeTestArgs:
    vault: str | None
    file: str | None
    json_out: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> KnowledgeTestArgs:
        return cls(
            vault=_optional_text(args, "vault"),
            file=_optional_text(args, "file"),
            json_out=_optional_bool(args, "json_out") or False,
        )


@dataclass(frozen=True)
class ResearchLoopArgs:
    vault: str | None
    task: str | None
    dry_run: bool
    force: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> ResearchLoopArgs:
        return cls(
            vault=_optional_text(args, "vault"),
            task=_optional_text(args, "task"),
            dry_run=_optional_bool(args, "dry_run") or False,
            force=_optional_bool(args, "force") or False,
        )


@dataclass(frozen=True)
class SecurityArgs:
    file: str

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> SecurityArgs:
        return cls(file=_required_text(args, "file"))


@dataclass(frozen=True)
class WakeupArgs:
    vault: str | None
    update_claude: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> WakeupArgs:
        return cls(
            vault=_optional_text(args, "vault"),
            update_claude=_optional_bool(args, "update_claude") or False,
        )


@dataclass(frozen=True)
class VaultArgs:
    vault: str | None

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> VaultArgs:
        return cls(vault=_optional_text(args, "vault"))


@dataclass(frozen=True)
class ConfigureArgs:
    vault: str | None
    wiki_root: str | None
    og_base_url: str | None
    viewer_enabled: bool | None
    git_enabled: bool | None
    research_enabled: bool | None
    security_enabled: bool | None
    persona_name: str | None

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> ConfigureArgs:
        return cls(
            vault=_optional_text(args, "vault"),
            wiki_root=_optional_text(args, "wiki_root"),
            og_base_url=_optional_text(args, "og_base_url"),
            viewer_enabled=_optional_bool(args, "viewer_enabled"),
            git_enabled=_optional_bool(args, "git_enabled"),
            research_enabled=_optional_bool(args, "research_enabled"),
            security_enabled=_optional_bool(args, "security_enabled"),
            persona_name=_optional_text(args, "persona_name"),
        )


@dataclass(frozen=True)
class SearchArgs:
    vault: str | None
    query: str
    limit: int
    tag: str | None
    scope: SearchScope

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> SearchArgs:
        scope = _required_text(args, "scope")
        if scope not in SEARCH_SCOPES:
            raise ValueError(f"scope must be one of: {', '.join(SEARCH_SCOPES)}")
        return cls(
            vault=_optional_text(args, "vault"),
            query=_required_text(args, "query"),
            limit=_positive_int(args, "limit"),
            tag=_optional_text(args, "tag") or None,
            scope=cast(SearchScope, scope),
        )
