"""TOTP (RFC 6238 vectors), secret encryption and MFA tokens."""

import base64
import uuid

import jwt
import pytest

from apps.api.auth import totp
from apps.api.auth.tokens import AccessClaims, InvalidTokenError, JwtSigner
from apps.api.crypto import CryptoError, SecretBox

RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()


@pytest.mark.parametrize(
    ("t", "expected"),
    [(59, "94287082"), (1111111109, "07081804"), (1111111111, "14050471"),
     (1234567890, "89005924"), (2000000000, "69279037")],
)  # fmt: skip
def test_rfc6238_sha1_vectors(t: int, expected: str) -> None:
    assert totp.code_at(RFC_SECRET, t // 30, digits=8) == expected


def test_verify_window_replay_and_format() -> None:
    secret, now = totp.new_secret(), 1_700_000_000.0
    step = totp.current_step(now)
    assert len(secret) == 32
    assert totp.verify(secret, totp.code_at(secret, step), now) == step
    assert totp.verify(secret, totp.code_at(secret, step - 1), now) == step - 1
    assert totp.verify(secret, totp.code_at(secret, step + 1), now) == step + 1
    assert totp.verify(secret, totp.code_at(secret, step + 2), now) is None
    assert totp.verify(secret, totp.code_at(secret, step), now, after_step=step) is None
    code = totp.code_at(secret, step)
    assert totp.verify(secret, f"{code[:3]} {code[3:]}", now) == step
    assert totp.verify(secret, "12ab56", now) is None and totp.verify(secret, "123", now) is None
    assert totp.current_step() > step
    uri = totp.provisioning_uri(secret, "ana@example.com")
    assert (
        uri.startswith("otpauth://totp/Smart%20QA%3Aana%40example.com?")
        and f"secret={secret}" in uri
    )


def test_secret_box() -> None:
    key = base64.b64encode(b"k" * 32).decode()
    box = SecretBox.from_b64(key)
    blob = box.seal("JBSWY3DP", b"ctx")
    assert b"JBSWY3DP" not in blob and box.open(blob, b"ctx") == "JBSWY3DP"
    for bad in (lambda: box.open(blob, b"other"), lambda: box.open(blob[:-1] + b"x", b"ctx"),
                lambda: box.open(b"\x02" + blob[1:], b"ctx"), lambda: SecretBox(b"short"),
                lambda: SecretBox.from_b64("not base64!")):  # fmt: skip
        with pytest.raises(CryptoError):
            bad()


def test_mfa_tokens_are_not_access_tokens() -> None:
    signer = JwtSigner.ephemeral()
    uid = uuid.uuid4()
    mfa_token = signer.issue_mfa(uid)
    assert signer.verify_mfa(mfa_token) == uid
    with pytest.raises(InvalidTokenError):
        signer.verify(mfa_token)
    with pytest.raises(InvalidTokenError):
        signer.verify_mfa(signer.issue(AccessClaims(uid, uuid.uuid4())))
    forged = jwt.encode(
        {"iss": "smart-qa", "sub": str(uid), "purpose": "reset", "exp": 9_999_999_999},
        signer._private, algorithm="EdDSA",
    )  # fmt: skip
    with pytest.raises(InvalidTokenError, match="not an MFA token"):
        signer.verify_mfa(forged)
