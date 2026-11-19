"""TOTP second factor (RFC 6238: HMAC-SHA1, 30-second steps, 6 digits), standard-library only.

`verify` accepts the current step and one step either side (clock drift) and returns the step it
matched, so the caller can refuse a code that was already used (replay protection).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

STEP_S = 30
DIGITS = 6
DRIFT_STEPS = 1


def new_secret() -> str:
    """160-bit random secret, base32 without padding (what authenticator apps expect)."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    padded = secret.upper() + "=" * (-len(secret) % 8)
    return base64.b32decode(padded)


def code_at(secret: str, step: int, digits: int = DIGITS) -> str:
    digest = hmac.new(_key(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**digits).zfill(digits)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // STEP_S)


def verify(
    secret: str, code: str, now: float | None = None, after_step: int | None = None
) -> int | None:
    """The matched step, or None. Steps at or before `after_step` (already used) never match."""
    code = code.strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    base = current_step(now)
    for step in range(base - DRIFT_STEPS, base + DRIFT_STEPS + 1):
        if after_step is not None and step <= after_step:
            continue
        if hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def provisioning_uri(secret: str, account: str, issuer: str = "Smart QA") -> str:
    label = quote(f"{issuer}:{account}")
    params = urlencode({"secret": secret, "issuer": issuer, "digits": DIGITS, "period": STEP_S})
    return f"otpauth://totp/{label}?{params}"
