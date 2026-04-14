"""Peers without bundled Python SDK: optional shell bridge or explicit skip."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from benchmarks.peers.base import PeerCapabilities, PeerHealth


class ExternalCmdPeerAdapter:
    """Run ``ENV_CMD`` with JSON on stdin; expect ``{"ranked_session_ids": [...]}`` on stdout."""

    def __init__(self, peer_id: str, *, env_var: str) -> None:
        self.peer_id = peer_id
        self._env_var = env_var

    def health(self) -> PeerHealth:
        cmd = os.environ.get(self._env_var, "").strip()
        if not cmd:
            return PeerHealth(
                ok=False,
                reason=f"{self._env_var} not set",
                detail=f"export {self._env_var}='path/to/script' to run this peer via JSON stdin/stdout",
            )
        return PeerHealth(ok=True)

    def capabilities(self) -> PeerCapabilities:
        return PeerCapabilities(
            peer_id=self.peer_id,
            display_name=self.peer_id,
            python_sdk=False,
            http_api=False,
            cli=True,
            mcp=False,
            requires_network=False,
            verbatim_ingest=False,
        )

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
        cmd = os.environ.get(self._env_var, "").strip()
        payload = {
            "sessions": sessions,
            "session_ids": session_ids,
            "dates": dates,
            "question": question,
            "n_fetch": n_fetch,
            "run_idx": run_idx,
        }
        proc = subprocess.run(
            cmd,
            shell=True,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=600,
            env=os.environ.copy(),
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"{self._env_var} failed rc={proc.returncode}: {(proc.stderr or proc.stdout)[:500]}"
            )
        out = json.loads(proc.stdout.strip())
        ids = out.get("ranked_session_ids") or out.get("session_ids") or []
        if not isinstance(ids, list):
            return []
        return [str(x) for x in ids]


class SupermemoryStubAdapter:
    """Placeholder until an official headless client is wired; health fails without API key."""

    peer_id = "supermemory"

    def health(self) -> PeerHealth:
        if os.environ.get("SUPERMEMORY_API_KEY"):
            return PeerHealth(
                ok=False,
                reason="supermemory client not bundled",
                detail="SUPERMEMORY_API_KEY is set but automated LME adapter is not implemented yet; use rubric_overrides.json for editorial scores.",
            )
        return PeerHealth(
            ok=False,
            reason="missing SUPERMEMORY_API_KEY",
            detail="Set SUPERMEMORY_API_KEY when a client is available, or rely on editorial dimension overrides.",
        )

    def capabilities(self) -> PeerCapabilities:
        return PeerCapabilities(
            peer_id=self.peer_id,
            display_name="supermemory",
            python_sdk=False,
            http_api=True,
            cli=False,
            mcp=False,
            requires_network=True,
            verbatim_ingest=False,
        )

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
        raise RuntimeError("supermemory adapter not implemented")


class UnavailablePeerAdapter:
    """Explicit skip with reason (used when registry resolves unknown id)."""

    def __init__(self, peer_id: str, reason: str) -> None:
        self.peer_id = peer_id
        self._reason = reason

    def health(self) -> PeerHealth:
        return PeerHealth(ok=False, reason=self._reason)

    def capabilities(self) -> PeerCapabilities:
        return PeerCapabilities(peer_id=self.peer_id, display_name=self.peer_id)

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
        raise RuntimeError(self._reason)
