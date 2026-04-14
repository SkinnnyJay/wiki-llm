"""Peer memory adapter contract for LongMemEval-style benchmarks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class PeerHealth:
    """Whether this peer can run in the current environment."""

    ok: bool
    reason: str = ""
    detail: str = ""


@dataclass
class PeerCapabilities:
    """Static metadata for integration / rubric scoring."""

    peer_id: str
    display_name: str = ""
    python_sdk: bool = False
    http_api: bool = False
    cli: bool = False
    mcp: bool = False
    requires_network: bool = False
    license_hint: str = ""
    verbatim_ingest: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class DimensionScores:
    """0–10 scores with provenance (plan: proxy | override | editorial | missing)."""

    data_integrity: float | None = None
    simplicity: float | None = None
    integration: float | None = None
    arch_maturity: float | None = None
    source: dict[str, str] = field(default_factory=dict)

    def overall(self) -> float | None:
        vals = [
            self.data_integrity,
            self.simplicity,
            self.integration,
            self.arch_maturity,
        ]
        present = [v for v in vals if v is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 2)


@runtime_checkable
class PeerAdapter(Protocol):
    """Ingest LME haystack text and answer with ranked session ids."""

    peer_id: str

    def health(self) -> PeerHealth:
        """Return whether the peer is runnable (deps, keys, binaries)."""
        ...

    def capabilities(self) -> PeerCapabilities:
        ...

    def ingest_and_query(
        self,
        *,
        sessions: list[list[dict[str, Any]]],
        session_ids: list[str],
        dates: list[str],
        question: str,
        n_fetch: int,
        run_idx: int,
        run_cache: Any,
    ) -> list[str]:
        """
        Index the haystack for one LME question, then search.

        Returns haystack_session_ids in best-first order (may be truncated).
        """
        ...
