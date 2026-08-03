"""mem0 (mem0ai) peer — optional pip install mem0ai; requires OPENAI_API_KEY for embeddings."""

from __future__ import annotations

import os
from typing import Any

from benchmarks.bench_harness import session_markdown_body
from benchmarks.peers.base import PeerCapabilities, PeerHealth


class Mem0PeerAdapter:
    peer_id = "mem0"

    def __init__(self, *, cache_root: Any) -> None:
        self._cache_root = cache_root
        self._memory = None
        self._last_roundtrip_ok: bool | None = None

    def _get_memory(self) -> Any:
        if self._memory is None:
            from mem0 import Memory

            self._memory = Memory()
        return self._memory

    def health(self) -> PeerHealth:
        try:
            import mem0  # noqa: F401
        except ImportError:
            return PeerHealth(
                ok=False,
                reason="mem0ai not installed",
                detail="pip install mem0ai (see requirements-optional.txt)",
            )
        if not os.environ.get("OPENAI_API_KEY"):
            # mem0 OSS often uses OpenAI embeddings
            if not os.environ.get("MEM0_API_KEY"):
                return PeerHealth(
                    ok=False,
                    reason="missing OPENAI_API_KEY",
                    detail="mem0 OSS embeddings typically need OPENAI_API_KEY in the environment",
                )
        return PeerHealth(ok=True)

    def capabilities(self) -> PeerCapabilities:
        return PeerCapabilities(
            peer_id=self.peer_id,
            display_name="mem0",
            python_sdk=True,
            http_api=True,
            cli=True,
            mcp=False,
            requires_network=True,
            license_hint="apache-2.0",
            verbatim_ingest=True,
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
        memory = self._get_memory()
        bench_uid = f"lme_q_{run_idx:05d}"
        bodies: dict[str, str] = {}
        for sid, sess, date in zip(session_ids, sessions, dates):
            body = session_markdown_body(sess, include_assistant=True)
            bodies[sid] = body
            memory.add(
                [{"role": "user", "content": body}],
                user_id=bench_uid,
                metadata={"session_id": sid, "bench_date": date},
                infer=False,
            )

        results = memory.search(question, user_id=bench_uid, limit=max(n_fetch, 20))

        ranked: list[str] = []
        seen: set[str] = set()

        def _extract_rows(r: Any) -> list[dict[str, Any]]:
            if isinstance(r, list):
                return [x for x in r if isinstance(x, dict)]
            if isinstance(r, dict):
                for k in ("results", "memories", "data"):
                    v = r.get(k)
                    if isinstance(v, list):
                        return [x for x in v if isinstance(x, dict)]
            return []

        rows = _extract_rows(results)
        for row in rows:
            sid = None
            meta = row.get("metadata") or row.get("meta") or {}
            if isinstance(meta, dict):
                sid = meta.get("session_id")
            if not sid and isinstance(row.get("memory"), str):
                # try hash match
                t = row["memory"]
                for s, b in bodies.items():
                    if t.strip()[:200] in b or b[:200] in t:
                        sid = s
                        break
            if isinstance(sid, str) and sid not in seen:
                seen.add(sid)
                ranked.append(sid)

        # Fallback: parse session_id from string fields
        if not ranked:
            for row in rows:
                txt = str(row.get("memory") or row.get("text") or "")
                for sid in session_ids:
                    if sid in txt and sid not in seen:
                        seen.add(sid)
                        ranked.append(sid)

        # Roundtrip signal for dimensions (first session only)
        roundtrip_ok: bool | None = None
        if session_ids and bodies:
            first = session_ids[0]
            try:
                r2 = memory.search(bodies[first][:120], user_id=bench_uid, limit=3)
                rows2 = _extract_rows(r2)
                if rows2:
                    t0 = str(rows2[0].get("memory") or "")
                    roundtrip_ok = len(t0) > 10 and (bodies[first][:80] in t0 or t0[:80] in bodies[first])
            except Exception:
                roundtrip_ok = None

        self._last_roundtrip_ok = roundtrip_ok
        return ranked

    def last_roundtrip_ok(self) -> bool | None:
        return self._last_roundtrip_ok
