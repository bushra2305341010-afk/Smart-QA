"""Runner-side encrypted identity vault (T-203). Test logins never reach the control plane.

The control plane stores only a reference (`identity.secret_ref = "vault:<name>"`) and compiled
tests carry `{{secret:<name>}}` placeholders. The values live in one file on the runner's machine,
encrypted with AES-256-GCM. The key comes from `SAQ_VAULT_KEY`: either 32 random bytes in
base64 (`saq vault keygen`) or a passphrase stretched with scrypt (salt stored in the file).
Writes are atomic (temp file + rename, mode 0600). A wrong key or a tampered file fails closed.
"""

from __future__ import annotations

import base64
import json
import os
import re
import secrets
import tempfile
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

NAME = re.compile(r"^[a-z0-9_]{1,40}$")
REF = re.compile(r"^(?:vault|env):[a-z0-9_]{1,40}$")
VERSION = 1
AAD = b"smart-qa-vault-v1"


class VaultError(Exception):
    pass


def new_key() -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode()


def _key(secret: str, salt: bytes) -> bytes:
    try:
        raw = base64.b64decode(secret, validate=True)
        if len(raw) == 32:
            return raw
    except ValueError:
        pass
    if len(secret) < 12:
        raise VaultError("SAQ_VAULT_KEY must be a 32-byte base64 key or a 12+ character passphrase")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(secret.encode())


class Vault:
    def __init__(self, path: Path, key: str) -> None:
        self.path, self._secret = path, key
        self._cache: dict[str, str] | None = None  # decrypted once per process for `get`

    def _load(self) -> tuple[bytes, dict[str, str]]:
        if not self.path.exists():
            return secrets.token_bytes(16), {}
        try:
            blob = json.loads(self.path.read_text())
            salt = base64.b64decode(blob["salt"])
            nonce = base64.b64decode(blob["nonce"])
            data = base64.b64decode(blob["data"])
            if blob.get("v") != VERSION:
                raise VaultError(f"Unsupported vault version {blob.get('v')}")
        except (ValueError, KeyError, TypeError) as exc:
            raise VaultError("Vault file is corrupt") from exc
        try:
            plain = AESGCM(_key(self._secret, salt)).decrypt(nonce, data, AAD)
        except InvalidTag:
            raise VaultError("Wrong vault key or tampered vault file") from None
        values: dict[str, str] = json.loads(plain)
        return salt, values

    def _save(self, salt: bytes, values: dict[str, str]) -> None:
        nonce = secrets.token_bytes(12)
        data = AESGCM(_key(self._secret, salt)).encrypt(nonce, json.dumps(values).encode(), AAD)
        blob = {
            "v": VERSION,
            "salt": base64.b64encode(salt).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "data": base64.b64encode(data).decode(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".vault-")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(blob, fh)
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def names(self) -> list[str]:
        return sorted(self._load()[1])

    def set(self, name: str, value: str) -> None:
        if not NAME.match(name):
            raise VaultError("Names are 1-40 characters: a-z, 0-9, _")
        salt, values = self._load()
        values[name] = value
        self._save(salt, values)
        self._cache = None

    def remove(self, name: str) -> bool:
        salt, values = self._load()
        found = values.pop(name, None) is not None
        if found:
            self._save(salt, values)
            self._cache = None
        return found

    def get(self, name: str) -> str | None:
        """`SecretSource` for the runner's resolver."""
        if self._cache is None:
            self._cache = self._load()[1]
        return self._cache.get(name)

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> Vault | None:
        env = dict(os.environ if environ is None else environ)
        path, key = env.get("SAQ_VAULT_FILE"), env.get("SAQ_VAULT_KEY")
        if not path:
            return None
        if not key:
            raise VaultError("SAQ_VAULT_FILE is set but SAQ_VAULT_KEY is missing")
        return cls(Path(path), key)
