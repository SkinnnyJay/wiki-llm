"""Peers without bundled Python SDK: optional command bridge or explicit skip."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from typing import Any, cast

from benchmarks.peers.base import PeerCapabilities, PeerHealth

EXTERNAL_PEER_TIMEOUT_SECONDS = 600


class ExternalCmdPeerAdapter:
    """Run a tokenized ``ENV_CMD`` with JSON stdin and ranked-session JSON stdout."""

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
        run_cache: object,
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
        try:
            command = shlex.split(cmd)
        except ValueError as exc:
            raise RuntimeError(f"{self._env_var} is not a valid command: {exc}") from exc
        if not command:
            raise RuntimeError(f"{self._env_var} is not a valid command")
        proc = subprocess.run(
            command,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=EXTERNAL_PEER_TIMEOUT_SECONDS,
            env=os.environ.copy(),
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"{self._env_var} failed rc={proc.returncode}: {(proc.stderr or proc.stdout)[:500]}"
            )
        try:
            decoded = cast(object, json.loads(proc.stdout.strip()))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{self._env_var} returned invalid JSON: {exc}") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError(f"{self._env_var} must return a JSON object")
        out = cast(dict[str, object], decoded)
        ids = out.get("ranked_session_ids") or out.get("session_ids") or []
        if not isinstance(ids, list):
            return []
        return [str(x) for x in ids]


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
        run_cache: object,
    ) -> list[str]:
        raise RuntimeError(self._reason)
