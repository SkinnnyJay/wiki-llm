"""Pluggable text compressors for benchmarks and optional wake-up context (lossy)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

# Default steno abbreviations (extend via config benchmark.steno.custom_abbreviations)
_DEFAULT_ABBREV: dict[str, str] = {
    "because": "bc",
    "should": "shd",
    "would": "wd",
    "could": "cd",
    "between": "btwn",
    "through": "thru",
    "without": "w/o",
    "function": "fn",
    "configuration": "cfg",
    "application": "app",
    "development": "dev",
    "environment": "env",
    "information": "info",
    "approximately": "approx",
    "authentication": "auth",
    "authorization": "authz",
    "implementation": "impl",
    "documentation": "docs",
    "infrastructure": "infra",
    "repository": "repo",
    "database": "db",
    "message": "msg",
    "response": "resp",
    "request": "req",
    "different": "diff",
    "important": "imp",
    "probably": "prob",
    "something": "sth",
    "everything": "evth",
}

_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "to", "of", "in", "for", "on", "with",
    "at", "by", "from", "as", "into", "about", "between", "through", "during",
    "before", "after", "above", "below", "up", "down", "out", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "so", "than", "too", "very", "just", "don", "now", "and", "but", "or",
    "if", "while", "that", "this", "these", "those", "it", "its", "i", "we",
    "you", "he", "she", "they", "me", "him", "her", "us", "them", "my", "your",
    "his", "our", "their", "what", "which", "who", "whom", "also", "much",
    "many", "like", "because", "since", "get", "got", "use", "used", "using",
    "make", "made", "thing", "things", "way", "well", "really", "want", "need",
}


class Compressor(Protocol):
    name: str

    def compress(self, text: str, *, metadata: dict[str, Any] | None = None) -> str: ...

    def stats(self, original: str, compressed: str) -> dict[str, Any]: ...


def _token_estimate(text: str) -> int:
    """Rough token count (~1.3 tokens per word)."""
    words = text.split()
    return max(1, int(len(words) * 1.3))


@dataclass
class RawCompressor:
    name: str = "raw"

    def compress(self, text: str, *, metadata: dict[str, Any] | None = None) -> str:
        return text

    def stats(self, original: str, compressed: str) -> dict[str, Any]:
        return {
            "original_tokens_est": _token_estimate(original),
            "compressed_tokens_est": _token_estimate(compressed),
            "ratio": round(_token_estimate(original) / max(_token_estimate(compressed), 1), 3),
        }


@dataclass
class StenoCompressor:
    """Vowel-drop + abbreviation table; preserves quoted strings and code-ish tokens."""

    name: str = "steno"
    vowel_drop_min_length: int = 5
    preserve_quoted: bool = True
    custom_abbreviations: dict[str, str] | None = None

    def __post_init__(self) -> None:
        self._abbrev = dict(_DEFAULT_ABBREV)
        if self.custom_abbreviations:
            self._abbrev.update({k.lower(): v for k, v in self.custom_abbreviations.items()})

    def compress(self, text: str, *, metadata: dict[str, Any] | None = None) -> str:
        if self.preserve_quoted:
            parts: list[str] = []
            for chunk in re.split(r'("[^"]*"|\'[^\']*\')', text):
                if len(chunk) >= 2 and chunk[0] in "\"'" and chunk[-1] == chunk[0]:
                    parts.append(chunk)
                else:
                    parts.append(self._compress_plain(chunk))
            return "".join(parts)
        return self._compress_plain(text)

    def _compress_plain(self, s: str) -> str:
        out: list[str] = []
        for word in re.split(r"(\s+)", s):
            if not word.strip() or word.isspace():
                out.append(word)
                continue
            w_clean = re.sub(r"^[^\w]+|[^\w]+$", "", word)
            if not w_clean:
                out.append(word)
                continue
            lower = w_clean.lower()
            if lower in self._abbrev:
                rep = self._abbrev[lower]
                out.append(word.replace(w_clean, rep))
                continue
            if len(w_clean) >= self.vowel_drop_min_length and w_clean.isalpha():
                dropped = "".join(c for c in w_clean if c.lower() not in "aeiou")
                if len(dropped) >= 2:
                    out.append(word.replace(w_clean, dropped))
                    continue
            out.append(word)
        return "".join(out)

    def stats(self, original: str, compressed: str) -> dict[str, Any]:
        o, c = _token_estimate(original), _token_estimate(compressed)
        return {"original_tokens_est": o, "compressed_tokens_est": c, "ratio": round(o / max(c, 1), 3)}


@dataclass
class PruneCompressor:
    """Remove stop words; keep lines with high token density."""

    name: str = "prune"
    removal_percentile: int = 30

    def compress(self, text: str, *, metadata: dict[str, Any] | None = None) -> str:
        lines = text.splitlines()
        out_lines: list[str] = []
        for line in lines:
            words = re.findall(r"\b[\w'-]+\b", line)
            if not words:
                out_lines.append(line)
                continue
            kept = [w for w in words if w.lower() not in _STOP_WORDS]
            if not kept:
                kept = words[: max(1, len(words) // 2)]
            ratio = len(kept) / max(len(words), 1)
            if ratio >= (100 - self.removal_percentile) / 100.0 or len(kept) >= 3:
                out_lines.append(" ".join(kept))
            elif line.strip():
                out_lines.append(" ".join(words[: max(3, len(words) // 2)]))
        return "\n".join(out_lines) if out_lines else text[:2000]

    def stats(self, original: str, compressed: str) -> dict[str, Any]:
        o, c = _token_estimate(original), _token_estimate(compressed)
        return {"original_tokens_est": o, "compressed_tokens_est": c, "ratio": round(o / max(c, 1), 3)}


@dataclass
class ExtractCompressor:
    """AAAK-style: entities + topics + one key sentence."""

    name: str = "extract"
    max_entities: int = 5
    max_topics: int = 3

    def compress(self, text: str, *, metadata: dict[str, Any] | None = None) -> str:
        meta = metadata or {}
        # Topics: word freq
        words = re.findall(r"[a-zA-Z][a-zA-Z_-]{2,}", text[:8000])
        freq: dict[str, int] = {}
        for w in words:
            wl = w.lower()
            if wl in _STOP_WORDS or len(wl) < 3:
                continue
            freq[wl] = freq.get(wl, 0) + 1
        topics = [t for t, _ in sorted(freq.items(), key=lambda x: -x[1])[: self.max_topics]]
        # Entities: TitleCase mid-sentence
        ents: list[str] = []
        for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", text):
            if m.group() not in ents:
                ents.append(m.group())
            if len(ents) >= self.max_entities:
                break
        # Key sentence: first long sentence with decision words
        decision = {"decided", "because", "chose", "instead", "prefer", "use", "using"}
        best = ""
        for sent in re.split(r"[.!?\n]+", text):
            s = sent.strip()
            if len(s) < 15:
                continue
            if any(d in s.lower() for d in decision) or len(s) < 120:
                best = s[:200]
                break
        if not best and text.strip():
            best = text.strip().split("\n")[0][:200]
        parts = [
            f"ENT: {','.join(ents)}" if ents else "ENT: ?",
            f"TOP: {'_'.join(topics)}" if topics else "TOP: misc",
            f"KEY: {best}" if best else "",
        ]
        return "\n".join(p for p in parts if p)

    def stats(self, original: str, compressed: str) -> dict[str, Any]:
        o, c = _token_estimate(original), _token_estimate(compressed)
        return {"original_tokens_est": o, "compressed_tokens_est": c, "ratio": round(o / max(c, 1), 3)}


@dataclass
class CompactCompressor:
    """Keep high-scoring sentences verbatim."""

    name: str = "compact"
    keep_percentile: int = 60
    min_sentence_score: float = 0.3

    def compress(self, text: str, *, metadata: dict[str, Any] | None = None) -> str:
        sentences = [s.strip() for s in re.split(r"[.!?\n]+", text) if len(s.strip()) > 10]
        if not sentences:
            return text[:4000]
        scored: list[tuple[float, str]] = []
        decision_words = {
            "decided", "because", "chose", "instead", "prefer", "important", "key",
            "api", "database", "deploy", "use", "using", "name", "called",
        }
        for s in sentences:
            sl = s.lower()
            score = sum(2 for w in decision_words if w in sl)
            score += min(3, len(re.findall(r"\b\d+\b", s)))
            score += min(5, len(re.findall(r"\b[A-Z][a-z]+\b", s)))
            if len(s) < 100:
                score += 0.5
            scored.append((score, s))
        scored.sort(key=lambda x: -x[0])
        n_keep = max(1, int(len(scored) * self.keep_percentile / 100.0))
        kept = [s for sc, s in scored[:n_keep] if sc >= self.min_sentence_score]
        if not kept:
            kept = [s for _, s in scored[: max(1, n_keep)]]
        return ". ".join(kept) + ("." if kept else "")

    def stats(self, original: str, compressed: str) -> dict[str, Any]:
        o, c = _token_estimate(original), _token_estimate(compressed)
        return {"original_tokens_est": o, "compressed_tokens_est": c, "ratio": round(o / max(c, 1), 3)}


def get_compressor(name: str, cfg: dict[str, Any]) -> Compressor:
    b = cfg.get("benchmark") or {}
    if name == "raw":
        return RawCompressor()
    if name == "steno":
        st = b.get("steno") or {}
        return StenoCompressor(
            vowel_drop_min_length=int(st.get("vowel_drop_min_length", 5)),
            preserve_quoted=bool(st.get("preserve_quoted", True)),
            custom_abbreviations=st.get("custom_abbreviations") or {},
        )
    if name == "prune":
        pr = b.get("prune") or {}
        return PruneCompressor(removal_percentile=int(pr.get("removal_percentile", 30)))
    if name == "extract":
        ex = b.get("extract") or {}
        return ExtractCompressor(
            max_entities=int(ex.get("max_entities", 5)),
            max_topics=int(ex.get("max_topics", 3)),
        )
    if name == "compact":
        co = b.get("compact") or {}
        return CompactCompressor(
            keep_percentile=int(co.get("keep_percentile", 60)),
            min_sentence_score=float(co.get("min_sentence_score", 0.3)),
        )
    raise ValueError(f"Unknown compressor: {name}")
