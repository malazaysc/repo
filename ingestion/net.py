"""SSRF-guarded HTTP fetching.

All server-side fetches of user-supplied URLs go through :func:`safe_get`,
which:

- allows only http/https,
- rejects hosts that resolve to private/loopback/link-local/reserved IPs
  (blocks cloud metadata, internal services, localhost),
- follows redirects manually, re-validating every hop (so a public URL can't
  302 into an internal address),
- streams the body and aborts past a byte cap (bounds memory).

Residual: a tiny resolve→connect DNS-rebinding window remains (we validate by
resolution, not by pinning the socket to the checked IP). The practical SSRF
vectors — metadata IPs and internal hostnames — resolve to private addresses
and are rejected, so this closes the real risk for this app.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

ALLOWED_SCHEMES = {"http", "https"}
MAX_REDIRECTS = 5


class UnsafeURLError(Exception):
    """Raised when a URL is disallowed (bad scheme, internal host, too large)."""


def _ip_is_public(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def assert_safe_url(url: str) -> None:
    """Raise UnsafeURLError unless the URL is http(s) and resolves only to public IPs."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError(f"scheme not allowed: {parsed.scheme or '(none)'}")
    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL has no host")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"cannot resolve host: {host}") from exc
    for info in infos:
        ip_str = info[4][0]
        if not _ip_is_public(ip_str):
            raise UnsafeURLError(f"host resolves to a non-public address: {host} -> {ip_str}")


def safe_get(
    url: str,
    *,
    max_bytes: int,
    timeout: float = 20.0,
    headers: dict | None = None,
) -> tuple[bytes, httpx.Response]:
    """SSRF-guarded GET. Returns (body_bytes, final_response).

    Raises UnsafeURLError for disallowed/oversized responses and httpx.HTTPError
    for transport/status failures.
    """
    merged = {**DEFAULT_HEADERS, **(headers or {})}
    current = url

    with httpx.Client(follow_redirects=False, timeout=timeout, headers=merged) as client:
        for _ in range(MAX_REDIRECTS + 1):
            assert_safe_url(current)
            with client.stream("GET", current) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        resp.raise_for_status()
                        raise UnsafeURLError("redirect without Location")
                    current = urljoin(current, location)
                    continue

                resp.raise_for_status()
                total = 0
                chunks: list[bytes] = []
                for chunk in resp.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise UnsafeURLError(f"response exceeds {max_bytes} bytes")
                    chunks.append(chunk)
                return b"".join(chunks), resp

    raise UnsafeURLError("too many redirects")


def safe_get_text(url: str, *, max_bytes: int, timeout: float = 20.0) -> str:
    body, resp = safe_get(url, max_bytes=max_bytes, timeout=timeout)
    return body.decode(resp.encoding or "utf-8", errors="replace")
