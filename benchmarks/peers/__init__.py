"""Optional peer memory backends for LongMemEval-style benchmarks."""

from benchmarks.peers.base import (
    DimensionScores,
    PeerAdapter,
    PeerCapabilities,
    PeerHealth,
)
from benchmarks.peers.dimensions import dimensions_to_jsonable, merge_dimension_scores
from benchmarks.peers.registry import (
    KNOWN_PEERS,
    default_peer_cache_root,
    get_peer_adapter,
)

__all__ = [
    "DimensionScores",
    "PeerAdapter",
    "PeerCapabilities",
    "PeerHealth",
    "KNOWN_PEERS",
    "default_peer_cache_root",
    "dimensions_to_jsonable",
    "get_peer_adapter",
    "merge_dimension_scores",
]
