"""Compile pipeline: knowledge CI gates after wiki merge."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def run_compile(
    vault: Path,
    cfg: dict[str, Any],
    *,
    skip_kg: bool = False,
    skip_site: bool = False,
    strict_schema: bool = False,
    json_out: bool = False,
    raw_path: str | None = None,
    write_stubs: bool = False,
) -> dict[str, Any]:
    """
    Gates only — does not auto-write topic pages under ``wiki/``
    (agent still merges raw→wiki). Optional ``write_stubs`` writes drafts under
    ``outputs/stubs/`` only.
    """
    from lib.emit import emit_json
    from lib.wiki_lint import lint_vault, write_lint_report

    steps: list[dict[str, Any]] = []
    exit_code = 0
    only_pages: list[str] | None = None

    missing = []
    for p in [vault / "config.json", vault / "wiki" / "index.md", vault / "CLAUDE.md"]:
        if not p.is_file():
            missing.append(str(p))
    if missing:
        steps.append({"step": "validate", "ok": False, "missing": missing})
        exit_code = 1
    else:
        steps.append({"step": "validate", "ok": True})

    compile_cfg = dict(cfg.get("compile") or {})
    if strict_schema:
        compile_cfg["schema_required"] = True
        compile_cfg["require_sources"] = True
        cfg = {**cfg, "compile": compile_cfg}

    if raw_path:
        from lib.claims import normalize_raw_rel, pages_citing_raw

        try:
            needle = normalize_raw_rel(raw_path)
        except ValueError as exc:
            steps.append({"step": "scope", "ok": False, "error": str(exc)})
            result = {
                "ok": False,
                "exit_code": 1,
                "vault": str(vault),
                "steps": steps,
                "hint": "Invalid --raw path; use a vault-relative raw/… path without '..'.",
            }
            if json_out:
                emit_json(result)
            else:
                print("compile: FAIL")
                print(f"  [fail] scope {exc}", file=sys.stderr)
            return result
        only_pages = pages_citing_raw(vault, needle)
        steps.append(
            {
                "step": "scope",
                "ok": True,
                "raw": needle,
                "pages": only_pages,
                "page_count": len(only_pages),
            }
        )

    lint_report = lint_vault(
        vault,
        cfg,
        check_schema=True if strict_schema else None,
        only_pages=only_pages,
    )
    report_path = write_lint_report(vault, lint_report)
    steps.append(
        {
            "step": "lint",
            "ok": bool(lint_report.get("ok")),
            "issues": lint_report.get("counts", {}).get("issues", 0),
            "report": str(report_path),
            "only_pages": only_pages,
        }
    )
    if not lint_report.get("ok"):
        exit_code = 1

    claims_path = vault / "outputs" / "claims.json"
    if claims_path.is_file():
        steps.append(
            {
                "step": "claims",
                "ok": True,
                "path": str(claims_path),
            }
        )

    do_stubs = bool(write_stubs) or bool(compile_cfg.get("auto_stubs", False))
    if do_stubs:
        from lib.claims import extract_vault_claims, write_claim_stubs

        stub_claims = extract_vault_claims(vault, only_pages=only_pages)
        stub_result = write_claim_stubs(vault, stub_claims, only_pages=only_pages)
        steps.append(
            {
                "step": "stubs",
                "ok": True,
                "count": stub_result.get("count", 0),
                "paths": stub_result.get("paths", []),
            }
        )

    if not skip_kg and (cfg.get("knowledge_graph") or {}).get("enabled", True):
        from lib.fact_checker import find_predicate_conflicts
        from lib.knowledge_graph import get_kg_backend, rebuild_knowledge_graph

        kg = get_kg_backend(vault, cfg)
        rebuild = rebuild_knowledge_graph(vault, cfg, backend=kg)
        kg = get_kg_backend(vault, cfg)
        triples = list(kg.all_triples())
        conflicts = find_predicate_conflicts(triples)
        ok_kg = len(conflicts) == 0
        if conflicts and bool(compile_cfg.get("fail_on_kg_conflicts", True)):
            exit_code = 1
            ok_kg = False
        steps.append(
            {
                "step": "kg",
                "ok": ok_kg,
                "skipped": False,
                "rebuild": rebuild,
                "conflicts": len(conflicts),
                "conflict_rows": [
                    {
                        "subject": c["subject"],
                        "predicate": c["predicate"],
                        "objects": c["objects"],
                    }
                    for c in conflicts[:20]
                ],
            }
        )
    else:
        steps.append({"step": "kg", "ok": True, "skipped": True})

    if not skip_site and (cfg.get("viewer") or {}).get("enabled", True):
        from lib.sitegen import build_site, site_is_stale

        if site_is_stale(vault):
            out = build_site(vault, cfg)
            steps.append(
                {
                    "step": "site",
                    "ok": True,
                    "skipped": False,
                    "built": True,
                    "output": str(out),
                }
            )
        else:
            steps.append(
                {
                    "step": "site",
                    "ok": True,
                    "skipped": False,
                    "built": False,
                    "reason": "up-to-date",
                }
            )
    else:
        steps.append({"step": "site", "ok": True, "skipped": True})

    result: dict[str, Any] = {
        "ok": exit_code == 0,
        "exit_code": exit_code,
        "vault": str(vault),
        "steps": steps,
        "hint": (
            "Compile gates check the wiki; topic pages are still written by "
            "/llm-wiki:ingest / wiki-ingest (or manual edits). "
            "Optional --stubs writes drafts under outputs/stubs/ only."
        ),
    }
    if json_out:
        emit_json(result)
    else:
        status = "OK" if exit_code == 0 else "FAIL"
        print(f"compile: {status}")
        for s in steps:
            name = s.get("step")
            ok = s.get("ok")
            extra = ""
            if name == "scope":
                extra = f" raw={s.get('raw')} pages={s.get('page_count')}"
            if name == "lint":
                extra = f" issues={s.get('issues')} report={s.get('report')}"
            if name == "claims":
                extra = f" path={s.get('path')}"
            if name == "stubs":
                extra = f" count={s.get('count')}"
            if name == "kg" and not s.get("skipped"):
                extra = f" conflicts={s.get('conflicts')}"
            if name == "site" and not s.get("skipped"):
                extra = f" built={s.get('built')}"
            print(f"  [{'ok' if ok else 'fail'}] {name}{extra}")
        if exit_code != 0:
            print(result["hint"], file=sys.stderr)
    return result
