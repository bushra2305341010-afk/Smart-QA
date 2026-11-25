"""Domain allow-list for the safe-action policy (docs/09-security.md §6, "Off-domain navigation").

A URL is allowed only when its scheme is http(s) and its host is the environment's base host or
matches an `allowed_hosts` entry. Entries are host names (`shop.test`), optional ports
(`localhost:8765`) or one-level-or-deeper wildcards (`*.example.com`, which does not match the
bare `example.com`). Matching ignores case and a trailing dot. Everything else (`javascript:`,
`data:`, `file:`, look-alike hosts, user-info tricks) is off-domain.
"""

from __future__ import annotations

from urllib.parse import urlsplit

SAFE_SCHEMES = frozenset({"http", "https"})
# Pages the browser shows before any navigation; they never reach the network.
BLANK_PAGES = frozenset({"about:blank"})


def _clean(host: str) -> str:
    return host.strip().rstrip(".").lower()


def split_host(url: str) -> tuple[str, str, int | None] | None:
    """(scheme, host, port) of an absolute URL, or None if it has no usable host."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return None
    host = _clean(parts.hostname or "")
    if not host:
        return None
    return parts.scheme.lower(), host, port


def _entry_matches(entry: str, host: str, port: int | None) -> bool:
    entry = _clean(entry)
    want_port: int | None = None
    if entry.count(":") == 1:  # host:port (IPv6 entries are not supported here)
        entry, _, raw = entry.partition(":")
        if not raw.isdigit():
            return False
        want_port = int(raw)
    if want_port is not None and want_port != port:
        return False
    if entry.startswith("*."):
        suffix = entry[1:]  # ".example.com"
        return host.endswith(suffix) and len(host) > len(suffix)
    return host == entry


def allowed_hosts_for(base_url: str, allowed_hosts: list[str]) -> list[str]:
    """The base URL's host:port is always allowed, plus the explicit entries."""
    entries = list(allowed_hosts)
    base = split_host(base_url)
    if base is not None:
        _, host, port = base
        entries.append(f"{host}:{port}" if port is not None else host)
    return entries


def is_allowed_url(url: str, base_url: str, allowed_hosts: list[str]) -> bool:
    if url.strip().lower() in BLANK_PAGES:
        return True
    parsed = split_host(url)
    if parsed is None:
        return False
    scheme, host, port = parsed
    if scheme not in SAFE_SCHEMES:
        return False
    return any(_entry_matches(e, host, port) for e in allowed_hosts_for(base_url, allowed_hosts))
