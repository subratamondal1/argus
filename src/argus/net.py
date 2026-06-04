"""SSRF guard for outbound fetches.

web_fetch and URL ingest follow LLM-chosen / user-supplied URLs, so an
adversarial page (or prompt) can name an internal address — 127.0.0.1, the
10.x/192.168.x LAN, or the cloud metadata endpoint 169.254.169.254. Before any
outbound GET, resolve the host and refuse if it lands on a private, loopback,
link-local, or otherwise non-public range. Resolution is blocking, so async
callers run it via asyncio.to_thread.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    """Raised when a URL is malformed or resolves to a non-public address."""


def assert_safe_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError(f"unsupported URL scheme: {parsed.scheme!r}")
    host: str | None = parsed.hostname
    if not host:
        raise UnsafeUrlError("URL has no host")
    port: int = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as error:
        raise UnsafeUrlError(f"could not resolve host {host!r}") from error
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            raise UnsafeUrlError(
                f"refusing to fetch a private/internal address ({address}) for host {host!r}"
            )
