"""Repository URL rules for read-only Git import (T-202): an SSRF guard used by the API and,
again, by the worker before it clones."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit


class GitImportError(Exception):
    pass


BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "metadata"}


def check_repo_url(url: str, protocols: tuple[str, ...] = ("https",)) -> str:
    """Validate a repo URL (SSRF guard); returns it without a `#ref` fragment.

    Allowed: the given schemes only, no user:password in the URL, never loopback or link-local
    addresses (cloud metadata endpoints). Private company hosts (e.g. an internal GitLab) are
    allowed. Names are not resolved here; the worker runs with the same rules.
    """
    parts = urlsplit(url)
    if parts.scheme not in protocols:
        raise GitImportError(f"Only {', '.join(protocols)} repository URLs are allowed")
    if parts.scheme == "file":
        return url.split("#", 1)[0]
    host = (parts.hostname or "").lower()
    if not host or parts.username or parts.password:
        raise GitImportError("Use a plain URL; pass the token separately")
    if host in BLOCKED_HOSTS or host.endswith(".localhost"):
        raise GitImportError("This host is not allowed")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return url.split("#", 1)[0]
    if ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast:
        raise GitImportError("This address is not allowed")
    return url.split("#", 1)[0]


def split_ref(uri: str) -> tuple[str, str | None]:
    """`https://host/repo.git#main` → (url, "main")."""
    url, _, ref = uri.partition("#")
    return url, ref or None
