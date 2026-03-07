"""URL validation to prevent SSRF attacks."""

from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Schemes that are safe to fetch
_ALLOWED_SCHEMES = {"http", "https"}


def is_safe_url(url: str) -> bool:
    """Check if a URL is safe to fetch (not targeting internal resources).

    Blocks:
    - Non-HTTP(S) schemes (file://, ftp://, gopher://, etc.)
    - Localhost and loopback addresses
    - Private/reserved IP ranges
    - Link-local and cloud metadata IPs
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in _ALLOWED_SCHEMES:
        logger.debug("Blocked URL with scheme %r: %s", parsed.scheme, url)
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # Block obvious localhost aliases
    if hostname in ("localhost", "0.0.0.0", "[::]", "[::1]"):
        logger.debug("Blocked localhost URL: %s", url)
        return False

    # Resolve hostname to IP and check against private ranges
    try:
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in addr_info:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                logger.debug("Blocked private/reserved IP %s for URL: %s", ip, url)
                return False
    except (socket.gaierror, ValueError, OSError):
        # If DNS resolution fails, allow it — feedparser/trafilatura will handle the error
        pass

    return True
