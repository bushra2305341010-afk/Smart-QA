"""Breached-password check (docs/10 §3, T-105b).

- `online`: Have I Been Pwned range API with k-anonymity: only the first 5 hex characters of
  the password's SHA-1 leave the machine; the response is padded. If the service is down the
  check fails open (sign-up still works) and a warning is logged.
- `offline`: a local file of SHA-1 hashes (`HASH` or `HASH:count` per line), for air-gapped
  installs.
- `off`: no check (default; air-gapped first).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Protocol

import httpx

log = logging.getLogger(__name__)
RANGE_API = "https://api.pwnedpasswords.com/range/"


class BreachChecker(Protocol):
    def is_breached(self, password: str) -> bool: ...


def sha1_hex(password: str) -> str:
    return hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()


class NoCheck:
    def is_breached(self, password: str) -> bool:
        return False


class OnlineChecker:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=5, headers={"Add-Padding": "true"})

    def is_breached(self, password: str) -> bool:
        digest = sha1_hex(password)
        prefix, suffix = digest[:5], digest[5:]
        try:
            res = self._client.get(RANGE_API + prefix)
            res.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("breached-password check unavailable, allowing: %s", exc)
            return False
        for line in res.text.splitlines():
            found, _, count = line.strip().partition(":")
            if found.upper() == suffix and count.strip() != "0":  # padding rows have count 0
                return True
        return False


class OfflineChecker:
    def __init__(self, path: Path) -> None:
        self._hashes = {
            line.split(":", 1)[0].strip().upper()
            for line in path.read_text().splitlines()
            if line.strip()
        }

    def is_breached(self, password: str) -> bool:
        return sha1_hex(password) in self._hashes
