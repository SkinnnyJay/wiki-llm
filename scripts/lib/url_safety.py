"""HTTP(S) URL validation for ingest — block file:// and common SSRF targets."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


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
        ip_str = info[4][0]
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
    if scheme not in ("http", "https"):
        raise SystemExit(
            f"{integration_name}: api_base_url must use http or https (got {scheme!r})."
        )
    host = (parsed.hostname or "").lower()
    if not host:
        raise SystemExit(f"{integration_name}: api_base_url has no hostname.")
    if host not in allowed_hosts:
        raise SystemExit(
            f"{integration_name}: api_base_url host {host!r} is not allowed. "
            f"Use one of: {', '.join(sorted(allowed_hosts))}."
        )
    port = parsed.port
    if port and port not in (80, 443):
        return f"{scheme}://{host}:{port}"
    return f"{scheme}://{host}"
