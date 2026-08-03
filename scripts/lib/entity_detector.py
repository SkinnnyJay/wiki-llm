"""Heuristic entity mentions for KG enrichment (complements wikilinks)."""
from __future__ import annotations

import re
from typing import Any

# Common English words to skip when treating Title Case tokens as entities.
_STOP = frozenset(
    ["The", "And", "But", "For", "With", "From", "Into", "About", "After", "Before", "During", "This", "That", "These", "Those", "When", "Where", "What", "Which", "Who", "How", "Why", "There", "Here", "Then", "Than", "They", "Them", "Their", "Some", "Any", "Each", "Every", "Other", "Such", "Same", "Very", "Much", "Too", "Not", "Yes", "All", "Can", "May", "Will", "Would", "Could", "Should", "Shall", "Might", "Must", "Has", "Have", "Had", "Was", "Were", "Been", "Being", "Does", "Did", "Do", "Is", "Are", "Am", "Been", "Being", "Your", "Our", "My", "Her", "His", "Its", "Their", "One", "Two", "Three", "First", "Next", "Last", "New", "Old", "Using", "Used", "Use", "Make", "Made", "Like", "Just", "Also", "Only", "Both", "Into", "Over", "Under", "Out", "Off", "Up", "Down"]
)


def extract_entities(text: str, *, max_entities: int = 24, cfg: dict[str, Any] | None = None) -> list[str]:
    """
    Find capitalized phrases and backtick identifiers as lightweight entity candidates.
    Deduped, ordered by first appearance.
    """
    cfg = cfg or {}
    kg = (cfg.get("knowledge_graph") or {}) if isinstance(cfg, dict) else {}
    if kg.get("entity_detection") is False:
        return []
    max_e = int(kg.get("entity_detection_max", max_entities))
    min_len = int(kg.get("entity_detection_min_len", 2))

    seen: set[str] = set()
    out: list[str] = []

    def push(s: str) -> None:
        s = s.strip()
        if len(s) < min_len:
            return
        if s in _STOP:
            return
        key = s.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(s)
        if len(out) >= max_e:
            return

    # [[Wiki Links]] targets already handled by KG rebuild — skip duplicates here via casing
    for m in re.finditer(r"\[\[([^\]|]+)", text):
        push(m.group(1).strip())

    # `identifier` or **Bold Title**
    for m in re.finditer(r"`([^`]{2,48})`", text):
        push(m.group(1).strip())
    for m in re.finditer(r"\*\*([^*]{2,48})\*\*", text):
        push(m.group(1).strip())

    # Title Case runs (2–4 tokens)
    for m in re.finditer(r"\b(?:[A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+){0,3})\b", text):
        phrase = m.group(0).strip()
        parts = phrase.split()
        if not parts:
            continue
        if len(parts) == 1 and parts[0] in _STOP:
            continue
        push(phrase)

    return out[:max_e]
