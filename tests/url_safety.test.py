# tests/url_safety.test.py
"""URL validation for ingest (scheme + SSRF guards)."""

from __future__ import annotations

import pytest

from lib.url_safety import validate_https_api_host, validate_public_http_url


def test_rejects_file_scheme():
    with pytest.raises(SystemExit, match="only http"):
        validate_public_http_url("file:///etc/passwd")


def test_rejects_ftp():
    with pytest.raises(SystemExit, match="only http"):
        validate_public_http_url("ftp://example.com/x")


def test_rejects_loopback_literal():
    with pytest.raises(SystemExit, match="not allowed"):
        validate_public_http_url("http://127.0.0.1/")


def test_rejects_private_literal():
    with pytest.raises(SystemExit, match="not allowed"):
        validate_public_http_url("https://192.168.1.1/")


def test_https_api_host_defaults():
    assert (
        validate_https_api_host(
            None,
            default_host="api.firecrawl.dev",
            allowed_hosts=frozenset({"api.firecrawl.dev"}),
            integration_name="firecrawl",
        )
        == "https://api.firecrawl.dev"
    )


def test_https_api_host_allowlisted():
    b = validate_https_api_host(
        "https://api.firecrawl.dev",
        default_host="api.firecrawl.dev",
        allowed_hosts=frozenset({"api.firecrawl.dev"}),
        integration_name="firecrawl",
    )
    assert b == "https://api.firecrawl.dev"


def test_https_api_host_rejects_evil_host():
    with pytest.raises(SystemExit, match="not allowed"):
        validate_https_api_host(
            "https://evil.example.com",
            default_host="api.firecrawl.dev",
            allowed_hosts=frozenset({"api.firecrawl.dev"}),
            integration_name="firecrawl",
        )


def test_public_resolves_to_public_ip(monkeypatch):
    import socket

    def fake_gai(host, port, family=0, type=0, proto=0, flags=0):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("93.184.216.34", 443),
            )
        ]

    monkeypatch.setattr("lib.url_safety.socket.getaddrinfo", fake_gai)
    assert validate_public_http_url("https://example.com/path").startswith("https://")


def test_public_resolves_to_loopback_blocked(monkeypatch):
    import socket

    def fake_gai(host, port, family=0, type=0, proto=0, flags=0):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("127.0.0.1", 443),
            )
        ]

    monkeypatch.setattr("lib.url_safety.socket.getaddrinfo", fake_gai)
    with pytest.raises(SystemExit, match="resolves to"):
        validate_public_http_url("https://example.com/")
