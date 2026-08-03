"""Tests for safe_fetch redirect SSRF guards."""

from __future__ import annotations

from typing import Any
from urllib.request import ProxyHandler

import pytest
from lib.url_safety import safe_fetch, validate_public_http_url


class _FakeSock:
    def __init__(self, peer: str = "93.184.216.34") -> None:
        self._peer = peer

    def getpeername(self) -> tuple[str, int]:
        return (self._peer, 443)


class _FakeRaw:
    def __init__(self, peer: str = "93.184.216.34") -> None:
        self._sock = _FakeSock(peer)


class _FakeFp:
    def __init__(self, peer: str | None = "93.184.216.34") -> None:
        self.raw = _FakeRaw(peer) if peer is not None else None
        self._sock = None


class _FakeResp:
    def __init__(
        self,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
        body: bytes = b"ok",
        reason: str = "OK",
        peer: str | None = "93.184.216.34",
    ) -> None:
        self.status = status
        self.headers = headers or {"Content-Type": "text/plain"}
        self.reason = reason
        self._body = body
        self._read = False
        self.fp = _FakeFp(peer)

    def read(self, _n: int = -1) -> bytes:
        if self._read:
            return b""
        self._read = True
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> _FakeResp:
        return self

    def __exit__(self, *args: object) -> None:
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


def test_safe_fetch_disables_ambient_proxy_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    handlers: tuple[object, ...] = ()

    class _Opener:
        def open(self, req: Any, timeout: float = 0) -> _FakeResp:
            return _FakeResp(body=b"hello")

    def fake_build_opener(*configured_handlers: object) -> _Opener:
        nonlocal handlers
        handlers = configured_handlers
        return _Opener()

    monkeypatch.setattr("lib.url_safety.build_opener", fake_build_opener)
    monkeypatch.setattr(
        "lib.url_safety.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:8080")

    safe_fetch("https://example.com/x")

    proxy_handlers = [handler for handler in handlers if isinstance(handler, ProxyHandler)]
    assert len(proxy_handlers) == 1
    assert proxy_handlers[0].proxies == {}


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


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"timeout": 0}, "timeout"),
        ({"max_redirects": -1}, "max_redirects"),
        ({"max_bytes": 0}, "max_bytes"),
    ],
)
def test_safe_fetch_rejects_invalid_limits(kwargs: dict[str, int], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        safe_fetch("https://example.com/x", **kwargs)


def test_safe_fetch_fails_closed_without_peer(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Opener:
        def open(self, req: Any, timeout: float = 0) -> _FakeResp:
            return _FakeResp(body=b"hello", peer=None)

    monkeypatch.setattr("lib.url_safety.build_opener", lambda *a, **k: _Opener())

    def fake_gai(host: str, *args: Any, **kwargs: Any) -> list:
        import socket

        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr("lib.url_safety.socket.getaddrinfo", fake_gai)
    monkeypatch.delenv("LLM_WIKI_SAFE_FETCH_ALLOW_MISSING_PEER", raising=False)
    with pytest.raises(SystemExit, match="could not verify connected peer"):
        safe_fetch("https://example.com/x")


def test_safe_fetch_rejects_blocked_peer(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Opener:
        def open(self, req: Any, timeout: float = 0) -> _FakeResp:
            return _FakeResp(body=b"secret", peer="127.0.0.1")

    monkeypatch.setattr("lib.url_safety.build_opener", lambda *a, **k: _Opener())

    def fake_gai(host: str, *args: Any, **kwargs: Any) -> list:
        import socket

        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr("lib.url_safety.socket.getaddrinfo", fake_gai)
    with pytest.raises(SystemExit, match="connected peer"):
        safe_fetch("https://example.com/x")
