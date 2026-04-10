"""Reciprocal rank fusion (RRF) for merging ranked lists of document paths."""

from __future__ import annotations


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    *,
    k: int = 60,
) -> list[str]:
    """RRF over path identifiers. Each list is paths best-first."""
    scores: dict[str, float] = {}
    for rlist in ranked_lists:
        for rank, path in enumerate(rlist):
            scores[path] = scores.get(path, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.keys(), key=lambda p: -scores[p])
