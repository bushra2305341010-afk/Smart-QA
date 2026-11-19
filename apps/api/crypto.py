"""AES-256-GCM for secrets at rest (docs/10 §5): TOTP secrets now, tracker tokens later.

Key: `SAQ_ENCRYPTION_KEY`, 32 random bytes in base64 (`python -c "import os,base64;
print(base64.b64encode(os.urandom(32)).decode())"`). Stored value = version byte + nonce + ct.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERSION = b"\x01"


class CryptoError(Exception):
    pass


class SecretBox:
    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise CryptoError("SAQ_ENCRYPTION_KEY must be 32 bytes (base64)")
        self._aead = AESGCM(key)

    @classmethod
    def from_b64(cls, value: str) -> SecretBox:
        try:
            return cls(base64.b64decode(value, validate=True))
        except ValueError as exc:
            raise CryptoError("SAQ_ENCRYPTION_KEY is not valid base64") from exc

    def seal(self, plaintext: str, context: bytes) -> bytes:
        nonce = os.urandom(12)
        return VERSION + nonce + self._aead.encrypt(nonce, plaintext.encode(), context)

    def open(self, blob: bytes, context: bytes) -> str:
        if blob[:1] != VERSION:
            raise CryptoError("Unknown ciphertext version")
        try:
            return self._aead.decrypt(blob[1:13], blob[13:], context).decode()
        except Exception as exc:  # InvalidTag: wrong key, wrong context or tampered
            raise CryptoError("Cannot decrypt secret") from exc
