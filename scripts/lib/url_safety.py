"""HTTP(S) URL validation for ingest — block file:// and common SSRF targets."""

from __future__ import annotations

import ipaddress
import logging
import os
import socket
from email.message import Message
from typing import Protocol, cast, runtime_checkable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import (
    HTTPErrorProcessor,
    HTTPHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from lib.http_defaults import DEFAULT_TIMEOUT_S, USER_AGENT

_log = logging.getLogger("llm_wiki.url_safety")

# Default fetch limits (overridable by callers).
DEFAULT_FETCH_TIMEOUT_S = DEFAULT_TIMEOUT_S
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_MAX_BYTES = 32 * 1024 * 1024
DEFAULT_USER_AGENT = USER_AGENT
READ_BLOCK_BYTES = 64 * 1024
REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
SAFE_FETCH_ALLOW_MISSING_PEER_ENV = "LLM_WIKI_SAFE_FETCH_ALLOW_MISSING_PEER"


class _FetchHeaders(Protocol):
    """The small, stable subset of HTTP headers used by safe_fetch."""

    def get(self, name: str, default: str | None = None) -> str | None: ...


class _FetchResponse(Protocol):
    """Response contract returned by urllib after the dynamic transport boundary."""

    headers: _FetchHeaders
    status: int | None
    reason: str
    fp: object | None

    def __enter__(self) -> _FetchResponse: ...

    def __exit__(self, *args: object) -> None: ...

    def getcode(self) -> int | None: ...

    def read(self, amount: int = -1) -> bytes: ...


@runtime_checkable
class _HasRaw(Protocol):
    raw: object | None


@runtime_checkable
class _HasSocket(Protocol):
    _sock: object | None


@runtime_checkable
class _PeerSocket(Protocol):
    def getpeername(self) -> tuple[str, ...]: ...


def validate_public_http_url(url: str, *, context: str = "URL") -> str:
    """
    Ensure url is http(s) with a public (non-loopback/private) resolved address.

    Raises SystemExit on failure. Returns the original URL string on success.
    """
    url = url.strip()
    if not url:
        raise SystemExit(f"{context}: empty URL")

    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise SystemExit(
            f"{context}: only http and https URLs are allowed (got scheme {scheme!r}; "
            "file:// and other schemes are blocked)."
        )

    host = parsed.hostname
    if not host:
        raise SystemExit(f"{context}: missing hostname in URL")

    # Reject bare IPv4/IPv6 literals in URL without resolution ambiguity
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if _is_blocked_ssrf_ip(host):
            raise SystemExit(f"{context}: address {host!r} is not allowed (private/loopback/link-local).")
        return url

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise SystemExit(f"{context}: could not resolve host {host!r}: {e}") from e

    seen: set[str] = set()
    for info in infos:
        sockaddr = info[4]
        ip_str = str(sockaddr[0])
        if ip_str in seen:
            continue
        seen.add(ip_str)
        if _is_blocked_ssrf_ip(ip_str):
            raise SystemExit(
                f"{context}: host {host!r} resolves to {ip_str}, which is not allowed "
                "(private network, loopback, link-local, or cloud metadata)."
            )

    if not seen:
        raise SystemExit(f"{context}: no addresses resolved for {host!r}")

    return url


def _is_blocked_ssrf_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    if ip.version == 4:
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or getattr(ip, "is_reserved", False)
            or ip == ipaddress.IPv4Address("0.0.0.0")
        ):
            return True
        # AWS / cloud instance metadata (IPv4)
        if ip_str == "169.254.169.254":
            return True
    else:
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or getattr(ip, "is_reserved", False)
            or getattr(ip, "is_unspecified", False)
        ):
            return True
    return False


def validate_https_api_host(
    configured: str | None,
    *,
    default_host: str,
    allowed_hosts: frozenset[str],
    integration_name: str,
) -> str:
    """
    Resolve integrations.*.api_base_url to an https origin using an allowlisted hostname.

    Raises SystemExit if the configured host is not allowed (prevents API key exfiltration).
    """
    if not configured or not str(configured).strip():
        return f"https://{default_host}"

    raw = str(configured).strip().rstrip("/")
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    scheme = (parsed.scheme or "https").lower()
    if scheme != "https":
        raise SystemExit(
            f"{integration_name}: api_base_url must use https (got {scheme!r})."
        )
    host = (parsed.hostname or "").lower()
    if not host:
        raise SystemExit(f"{integration_name}: api_base_url has no hostname.")
    if host not in allowed_hosts:
        raise SystemExit(
            f"{integration_name}: api_base_url host {host!r} is not allowed. "
            f"Use one of: {', '.join(sorted(allowed_hosts))}."
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise SystemExit(
            f"{integration_name}: api_base_url has an invalid port."
        ) from exc
    if port and port != 443:
        return f"https://{host}:{port}"
    return f"https://{host}"


class _NoRedirect(HTTPErrorProcessor):
    """Return 3xx responses to the caller instead of following them."""

    def http_response(self, request: Request, response: object) -> object:
        return response

    https_response = http_response


def _peer_ip_from_response(resp: _FetchResponse) -> str | None:
    """Best-effort peer IP from an urllib response (post-connect SSRF check)."""
    fp = resp.fp
    if not isinstance(fp, _HasRaw | _HasSocket):
        return None
    raw = fp.raw if isinstance(fp, _HasRaw) else None
    sock = raw._sock if isinstance(raw, _HasSocket) else None
    if sock is None and isinstance(fp, _HasSocket):
        sock = fp._sock
    if not isinstance(sock, _PeerSocket):
        return None
    try:
        peer = sock.getpeername()
    except OSError:
        return None
    if not peer:
        return None
    return str(peer[0])


def _assert_peer_allowed(resp: _FetchResponse, *, context: str, url: str) -> None:
    peer = _peer_ip_from_response(resp)
    if peer is None:
        allow_missing = os.environ.get(
            SAFE_FETCH_ALLOW_MISSING_PEER_ENV, ""
        ).strip().lower() in ("1", "true", "yes")
        if allow_missing:
            _log.warning(
                "safe_fetch: could not read peer IP for %r "
                "(%s set)",
                url,
                SAFE_FETCH_ALLOW_MISSING_PEER_ENV,
            )
            return
        raise SystemExit(
            f"{context}: could not verify connected peer IP for {url!r} "
            f"(fail closed; set {SAFE_FETCH_ALLOW_MISSING_PEER_ENV}=1 only if required)"
        )
    if _is_blocked_ssrf_ip(peer):
        raise SystemExit(
            f"{context}: connected peer {peer!r} is not allowed "
            f"(private/loopback/link-local/metadata) for {url!r}"
        )


def safe_fetch(
    url: str,
    *,
    context: str = "URL",
    timeout: float = DEFAULT_FETCH_TIMEOUT_S,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    max_bytes: int = DEFAULT_MAX_BYTES,
    user_agent: str = DEFAULT_USER_AGENT,
    headers: dict[str, str] | None = None,
) -> tuple[bytes, str, str]:
    """
    Fetch ``url`` with SSRF checks on the initial URL and every redirect hop.

    Does not follow redirects automatically: each Location is re-validated.
    After connect, re-checks the peer IP when available (DNS rebinding mitigation).
    Returns ``(body_bytes, final_url, content_type)``.
    Raises SystemExit on policy violations; URLError/HTTPError may propagate.
    """
    if timeout <= 0:
        raise ValueError("safe_fetch timeout must be greater than zero")
    if max_redirects < 0:
        raise ValueError("safe_fetch max_redirects cannot be negative")
    if max_bytes <= 0:
        raise ValueError("safe_fetch max_bytes must be greater than zero")

    current = validate_public_http_url(url, context=context)
    hdrs = {"User-Agent": user_agent}
    if headers:
        hdrs.update(headers)

    # Do not honor HTTP(S)_PROXY from the ambient process environment: proxying
    # hands URL routing to another process and defeats direct peer verification.
    opener = build_opener(ProxyHandler({}), HTTPHandler(), HTTPSHandler(), _NoRedirect())

    for hop in range(max_redirects + 1):
        req = Request(current, headers=hdrs, method="GET")
        try:
            with cast(_FetchResponse, opener.open(req, timeout=timeout)) as resp:
                _assert_peer_allowed(resp, context=context, url=current)
                status = resp.status or resp.getcode()
                if status in REDIRECT_STATUS_CODES:
                    loc = resp.headers.get("Location")
                    if not loc:
                        raise SystemExit(f"{context}: redirect without Location")
                    nxt = urljoin(current, loc)
                    _log.info("safe_fetch redirect hop=%s from=%r to=%r", hop, current, nxt)
                    current = validate_public_http_url(nxt, context=f"{context} (redirect)")
                    continue
                if status and int(status) >= 400:
                    raise HTTPError(
                        current,
                        int(status),
                        resp.reason,
                        cast(Message, resp.headers),
                        None,
                    )
                chunks: list[bytes] = []
                total = 0
                while True:
                    block = resp.read(READ_BLOCK_BYTES)
                    if not block:
                        break
                    total += len(block)
                    if total > max_bytes:
                        raise SystemExit(
                            f"{context}: response exceeds max_bytes={max_bytes}"
                        )
                    chunks.append(block)
                body = b"".join(chunks)
                ct = resp.headers.get("Content-Type", "") or ""
                return body, current, ct
        except HTTPError as e:
            if e.code in REDIRECT_STATUS_CODES:
                loc = e.headers.get("Location") if e.headers else None
                if not loc:
                    raise SystemExit(f"{context}: redirect without Location") from e
                nxt = urljoin(current, loc)
                current = validate_public_http_url(nxt, context=f"{context} (redirect)")
                continue
            raise
        except URLError:
            raise

    raise SystemExit(f"{context}: too many redirects (max {max_redirects})")
