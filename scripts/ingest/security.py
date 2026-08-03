"""Deterministic prompt-injection heuristics for raw markdown."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Rule id -> regex (case-insensitive) or callable
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ignore_prev_instr", re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", re.IGNORECASE)),
    ("system_prompt", re.compile(r"\b(system|developer)\s*:\s*you\s+are\b", re.IGNORECASE)),
    ("jailbreak_dan", re.compile(r"\bDAN\b.*\b(do anything now)\b", re.IGNORECASE)),
    ("override_policy", re.compile(r"disregard\s+(your|the)\s+(rules|guidelines|policy)", re.IGNORECASE)),
    ("role_hijack", re.compile(r"you\s+are\s+now\s+(in|a)\s+", re.IGNORECASE)),
    ("xml_tool", re.compile(r"<\s*(system|instruction|prompt)\s*>", re.IGNORECASE)),
]


@dataclass
class ScanResult:
    prompt_injection: str  # suspected | low_risk | unknown
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"prompt_injection": self.prompt_injection, "signals": self.signals}


def scan_text(text: str) -> ScanResult:
    signals: list[str] = []
    for rule_id, pat in PATTERNS:
        if pat.search(text):
            signals.append(rule_id)
    if signals:
        return ScanResult("suspected", signals)
    if len(text) > 50000 and text.count("```") > 40:
        return ScanResult("unknown", ["high_fence_density"])
    return ScanResult("low_risk", [])


def inject_frontmatter(body: str, security: dict[str, Any]) -> str:
    """Prepend or merge llm_wiki_security YAML frontmatter."""
    fm = (
        "---\n"
        f"llm_wiki_security:\n"
        f"  prompt_injection: {security['prompt_injection']!r}\n"
        f"  signals: {json.dumps(security['signals'])}\n"
        "---\n\n"
    )
    if body.startswith("---"):
        # naive: insert after first closing ---
        end = body.find("\n---", 3)
        if end != -1:
            return body[: end + 4] + "\n" + fm + body[end + 4 :].lstrip("\n")
    return fm + body


def write_sidecar(md_path: Path, result: ScanResult) -> None:
    p = md_path.with_suffix(md_path.suffix + ".security.json")
    p.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")


def scan_file(
    md_path: Path,
    cfg: dict[str, Any],
    *,
    force: bool = False,
) -> ScanResult | None:
    sec = cfg.get("ingestion_security") or {}
    if not force and not sec.get("enabled", False):
        return None
    text = md_path.read_text(encoding="utf-8", errors="replace")
    result = scan_text(text)
    if sec.get("log_to_raw_frontmatter", True):
        merged = inject_frontmatter(text, result.to_dict())
        md_path.write_text(merged, encoding="utf-8")
    else:
        write_sidecar(md_path, result)
    return result
