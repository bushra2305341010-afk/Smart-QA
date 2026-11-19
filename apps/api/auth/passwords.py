"""Password hashing (Argon2id) and the password rule (docs/10 §3).

Rule: at least 12 characters, at most 1024, no composition rules. The breached-password check
(k-anonymity) is tracked separately and plugs in at `check_password_rule`.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MIN_LENGTH = 12
MAX_LENGTH = 1024

_hasher = PasswordHasher()  # argon2id with the library's current recommended parameters


def check_password_rule(password: str) -> str | None:
    """Return a human message if the password breaks the rule, else None."""
    if len(password) < MIN_LENGTH:
        return f"Password must be at least {MIN_LENGTH} characters"
    if len(password) > MAX_LENGTH:
        return f"Password must be at most {MAX_LENGTH} characters"
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


# Verified against when the email is unknown, so response time does not reveal which emails exist.
DUMMY_HASH = hash_password("dummy-password-for-timing")
