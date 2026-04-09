"""Run tasks from research-tasks.json or .yaml (CLI research-loop)."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from lib.hooks import maybe_play_sound
from lib.ingest_finish import post_ingest
from ingest.registry import run_ingest


def _yaml_load(text: str, *, path: Path, explicit_suffix: bool) -> Any:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as e:
        msg = (
            "YAML task files require: pip install pyyaml"
            if explicit_suffix
            else f"Unrecognized tasks file {path.name}: use .json or install pyyaml for YAML."
        )
        raise SystemExit(msg) from e
    return yaml.safe_load(text)


def load_tasks_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    suf = path.suffix.lower()
    data: Any
    if suf == ".json":
        data = json.loads(text)
    elif suf in (".yaml", ".yml"):
        data = _yaml_load(text, path=path, explicit_suffix=True)
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = _yaml_load(text, path=path, explicit_suffix=False)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise SystemExit(f"Tasks file must be a mapping at root: {path}")
    return data


def _post_ingest_quiet(vault: Path, cfg: dict, path: Path, force: bool) -> int:
    return post_ingest(vault, cfg, path, force=force, force_security=False, suppress_sound=True)


def _run_task_ingest(
    vault: Path,
    cfg: dict,
    adapter: str,
    argv: list[str],
    force_adapter: bool,
) -> int:
    result = run_ingest(vault, cfg, adapter, argv, force_adapter=force_adapter)
    print(result.message)
    return _post_ingest_quiet(vault, cfg, result.output_path, force_adapter)


# Search adapters that support the `search_multi` fan-out, in priority order.
# Each entry: (adapter_id, env_var_or_empty)
_SEARCH_PROVIDERS: list[tuple[str, str]] = [
    ("brave", "BRAVE_SEARCH_API_KEY"),
    ("perplexity", "PERPLEXITY_API_KEY"),
    ("hackernews", ""),   # no key needed; query maps to top-stories fetch
]


def _available_search_providers(cfg: dict) -> list[str]:
    """Return provider ids that are enabled and have a key (or need no key)."""
    available = []
    integrations = cfg.get("integrations") or {}
    for pid, env_var in _SEARCH_PROVIDERS:
        slice_ = integrations.get(pid) or {}
        enabled = slice_.get("enabled", True)
        if not enabled:
            continue
        if env_var and not os.environ.get(slice_.get("api_key_env") or env_var):
            continue
        available.append(pid)
    return available


def run_research_loop(
    vault: Path,
    cfg: dict[str, Any],
    *,
    task_id: str | None = None,
    dry_run: bool = False,
    force_adapter: bool = False,
) -> int:
    rcfg = cfg.get("research_loop") or {}
    if not rcfg.get("enabled"):
        if dry_run:
            print("Note: research_loop.enabled is false (dry-run listing only).", file=sys.stderr)
        else:
            print("research_loop.enabled is false in config.json — enable it or use ingest manually.", file=sys.stderr)
            return 1
    rel = rcfg.get("tasks_file") or "research-tasks.json"
    path = vault / rel
    if not path.is_file():
        print(f"Missing tasks file: {path}", file=sys.stderr)
        return 1
    data = load_tasks_file(path)
    tasks = data.get("tasks") or []
    if not isinstance(tasks, list):
        print("research-tasks: 'tasks' must be a list", file=sys.stderr)
        return 1
    max_n = int(rcfg.get("max_items_per_run") or 8)
    delay = float(rcfg.get("delay_seconds_between_fetches") or 1.0)
    ran = 0
    exit_code = 0
    for t in tasks:
        if not isinstance(t, dict):
            continue
        if not t.get("run"):
            continue
        tid = str(t.get("id") or "")
        if task_id and tid != task_id:
            continue
        source = str(t.get("source") or "")
        if dry_run:
            print(f"[dry-run] task {tid!r} source={source!r}")
            ran += 1
            continue
        try:
            if source == "hackernews_top":
                depth = str(t.get("depth") or "stories")
                prefix = str(t.get("output_prefix") or "research/hn")
                out = f"{prefix}-top.md"
                argv = ["--limit", str(max_n), "--depth", depth, "--out", out]
                code = _run_task_ingest(vault, cfg, "hackernews", argv, force_adapter)
                if code != 0:
                    exit_code = code

            elif source == "fetch_urls":
                urls = t.get("urls") or []
                if not isinstance(urls, list):
                    print(f"task {tid}: urls must be a list", file=sys.stderr)
                    exit_code = 1
                    ran += 1
                    continue
                base_out = str(t.get("output_prefix") or "research/fetch")
                batch = [u.strip() for u in urls if isinstance(u, str) and u.strip()][:max_n]
                for i, u in enumerate(batch):
                    out = f"{base_out}-{i}.md"
                    code = _run_task_ingest(vault, cfg, "url", [u, "--out", out], force_adapter)
                    if code != 0:
                        exit_code = code
                    if delay and i < len(batch) - 1:
                        time.sleep(delay)

            elif source == "brave_search":
                # Single Brave Search query → raw/
                query = str(t.get("query") or "")
                if not query:
                    print(f"task {tid}: brave_search requires 'query'", file=sys.stderr)
                    exit_code = 1
                    ran += 1
                    continue
                mode = str(t.get("mode") or "llm-context")
                count = int(t.get("count") or max_n)
                prefix = str(t.get("output_prefix") or "research/brave")
                slug = query.lower().replace(" ", "_")[:40]
                out = f"{prefix}_{mode}_{slug}.md"
                argv = [query, "--mode", mode, "--count", str(count), "--out", out]
                if t.get("freshness"):
                    argv += ["--freshness", str(t["freshness"])]
                if t.get("goggles"):
                    argv += ["--goggles", str(t["goggles"])]
                code = _run_task_ingest(vault, cfg, "brave", argv, force_adapter)
                if code != 0:
                    exit_code = code

            elif source == "search_multi":
                # Fan out the same query to ALL available search providers and save
                # separate files — agents aggregate after all writes complete.
                query = str(t.get("query") or "")
                if not query:
                    print(f"task {tid}: search_multi requires 'query'", file=sys.stderr)
                    exit_code = 1
                    ran += 1
                    continue
                providers_raw = t.get("providers")
                if providers_raw is None:
                    providers = _available_search_providers(cfg)
                elif isinstance(providers_raw, str):
                    providers = [providers_raw.strip()] if providers_raw.strip() else _available_search_providers(cfg)
                elif isinstance(providers_raw, list):
                    providers = providers_raw
                else:
                    print(
                        f"task {tid}: search_multi 'providers' must be a list of ids (or omit for auto)",
                        file=sys.stderr,
                    )
                    exit_code = 1
                    ran += 1
                    continue

                count = int(t.get("count") or max_n)
                prefix = str(t.get("output_prefix") or "research/multi")
                slug = query.lower().replace(" ", "_")[:40]

                print(f"search_multi: dispatching {len(providers)} providers for: {query!r}")
                for pid in providers:
                    if pid == "brave":
                        mode = str(t.get("brave_mode") or "llm-context")
                        out = f"{prefix}/brave_{mode}_{slug}.md"
                        argv = [query, "--mode", mode, "--count", str(count), "--out", out]
                    elif pid == "perplexity":
                        out = f"{prefix}/perplexity_{slug}.md"
                        argv = [query, "--out", out]
                    elif pid == "hackernews":
                        out = f"{prefix}/hn_{slug}.md"
                        argv = ["--limit", str(min(count, 10)), "--out", out]
                    else:
                        print(f"  skip unknown provider {pid!r}", file=sys.stderr)
                        continue
                    try:
                        code = _run_task_ingest(vault, cfg, pid, argv, force_adapter)
                        if code != 0:
                            exit_code = code
                    except SystemExit as e:
                        print(f"  {pid}: {e}", file=sys.stderr)
                        exit_code = 1
                    if delay:
                        time.sleep(delay)

            else:
                print(
                    f"Unknown research task source {source!r} for task {tid!r} — "
                    "extend lib/research_loop.py",
                    file=sys.stderr,
                )
                exit_code = 1
                ran += 1
                continue
        except SystemExit as e:
            print(e, file=sys.stderr)
            c = e.code
            exit_code = int(c) if isinstance(c, int) else 1
            ran += 1
            continue
        ran += 1
        if source == "hackernews_top" and delay:
            time.sleep(delay)
    if ran == 0:
        if task_id:
            print(f"No runnable task with id={task_id!r} (check run: true).", file=sys.stderr)
        else:
            print("No tasks with run: true — edit research tasks file or use --dry-run.", file=sys.stderr)
        return 1 if not dry_run else 0
    if not dry_run and exit_code == 0 and ran > 0:
        maybe_play_sound(cfg, "research_loop")
    return exit_code
