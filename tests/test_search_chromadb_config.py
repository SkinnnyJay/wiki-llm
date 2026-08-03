"""Dependency-free contract tests for optional Chroma search configuration."""

from __future__ import annotations

import pytest
from lib.search_chromadb import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_DISTANCE_FUNCTION,
    _distance_function,
    _positive_batch_size,
)


@pytest.mark.parametrize("value", [0, -1, True, "bad", 100_001])
def test_invalid_chroma_batch_size_uses_safe_default(value: object) -> None:
    assert _positive_batch_size(value) == DEFAULT_BATCH_SIZE


def test_chroma_batch_size_accepts_bounded_numeric_text() -> None:
    assert _positive_batch_size("250") == 250


@pytest.mark.parametrize("value", [None, "unknown", "COSINE "])
def test_invalid_chroma_distance_function_uses_safe_default(value: object) -> None:
    expected = "cosine" if value == "COSINE " else DEFAULT_DISTANCE_FUNCTION
    assert _distance_function(value) == expected
