"""Run tasks from research-tasks.json or .yaml (CLI research-loop)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from lib.hooks import maybe_play_sound
from lib.ingest_finish import post_ingest
from ingest.registry import run_ingest


def load_tasks_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    suf = path.suffix.lower()
    data: Any
    if suf == ".json":
        data = json.loads(text)
    elif suf in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as e:
            raise SystemExit("YAML task files require: pip install pyyaml") from e
        data = yaml.safe_load(text)
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            try:
                import yaml  # type: ignore[import-untyped]
            except ImportError as e:
                raise SystemExit(
                    f"Unrecognized tasks file {path.name}: use .json or install pyyaml for YAML."
                ) from e
            data = yaml.safe_load(text)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise SystemExit(f"Tasks file must be a mapping at root: {path}")
    return data


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
                result = run_ingest(vault, cfg, "hackernews", argv, force_adapter=force_adapter)
                print(result.message)
                code = post_ingest(
                    vault,
                    cfg,
                    result.output_path,
                    force=force_adapter,
                    force_security=False,
                    suppress_sound=True,
                )
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
                    result = run_ingest(vault, cfg, "url", [u, "--out", out], force_adapter=force_adapter)
                    print(result.message)
                    code = post_ingest(
                        vault,
                        cfg,
                        result.output_path,
                        force=force_adapter,
                        force_security=False,
                        suppress_sound=True,
                    )
                    if code != 0:
                        exit_code = code
                    if delay and i < len(batch) - 1:
                        time.sleep(delay)
            else:
                print(f"Unknown research task source {source!r} for task {tid!r} — extend lib/research_loop.py", file=sys.stderr)
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
