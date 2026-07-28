"""Tests for safe_fetch redirect SSRF guards."""

from __future__ import annotations

from typing import Any

import pytest

from lib.url_safety import safe_fetch, validate_public_http_url


class _FakeResp:
    def __init__(
        self,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
        body: bytes = b"ok",
        reason: str = "OK",
    ) -> None:
        self.status = status
        self.headers = headers or {"Content-Type": "text/plain"}
        self.reason = reason
        self._body = body
        self._read = False

    def read(self, _n: int = -1) -> bytes:
        if self._read:
            return b""
        self._read = True
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> _FakeResp:
        return self

    def __exit__(self, *args: Any) -> None:
        return None


def test_safe_fetch_rejects_redirect_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class _Opener:
        def open(self, req: Any, timeout: float = 0) -> _FakeResp:
            url = req.full_url if hasattr(req, "full_url") else str(req.get_full_url())
            calls.append(url)
            if "evil.example" in url or url.startswith("https://public.example"):
                return _FakeResp(
                    status=302,
                    headers={"Location": "http://127.0.0.1/secret", "Content-Type": "text/plain"},
                    body=b"",
                )
            return _FakeResp(body=b"should not reach")

    monkeypatch.setattr(
        "lib.url_safety.build_opener",
        lambda *a, **k: _Opener(),
    )

    def fake_gai(host: str, *args: Any, **kwargs: Any) -> list:
        import socket

        if host in ("127.0.0.1", "localhost"):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr("lib.url_safety.socket.getaddrinfo", fake_gai)

    with pytest.raises(SystemExit, match="not allowed"):
        safe_fetch("https://public.example/start", context="test")


def test_safe_fetch_ok_no_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Opener:
        def open(self, req: Any, timeout: float = 0) -> _FakeResp:
            return _FakeResp(body=b"hello", headers={"Content-Type": "text/plain"})

    monkeypatch.setattr("lib.url_safety.build_opener", lambda *a, **k: _Opener())

    def fake_gai(host: str, *args: Any, **kwargs: Any) -> list:
        import socket

        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr("lib.url_safety.socket.getaddrinfo", fake_gai)
    body, final, ct = safe_fetch("https://example.com/x")
    assert body == b"hello"
    assert "example.com" in final
    assert "text/plain" in ct


def test_validate_still_blocks_file() -> None:
    with pytest.raises(SystemExit, match="only http"):
        validate_public_http_url("file:///etc/passwd")


def test_safe_fetch_rejects_oversized_body(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Opener:
        def open(self, req: Any, timeout: float = 0) -> _FakeResp:
            return _FakeResp(body=b"0123456789abcdef", headers={"Content-Type": "text/plain"})

    monkeypatch.setattr("lib.url_safety.build_opener", lambda *a, **k: _Opener())

    def fake_gai(host: str, *args: Any, **kwargs: Any) -> list:
        import socket

        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr("lib.url_safety.socket.getaddrinfo", fake_gai)
    with pytest.raises(SystemExit, match="max_bytes"):
        safe_fetch("https://example.com/big", max_bytes=10)
