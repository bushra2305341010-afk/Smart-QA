"""Breached-password check (T-105b): k-anonymity online, offline file, off."""

from pathlib import Path

import httpx
import pytest

from apps.api import main
from apps.api.auth.breached import NoCheck, OfflineChecker, OnlineChecker, sha1_hex
from apps.api.settings import Settings
from tests.api.conftest import PASSWORD

LEAKED = "password1234567"


def _online(handler) -> OnlineChecker:  # type: ignore[no-untyped-def]
    return OnlineChecker(httpx.Client(transport=httpx.MockTransport(handler)))


def test_online_sends_only_the_prefix() -> None:
    seen: list[str] = []
    digest = sha1_hex(LEAKED)

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(str(req.url))
        body = f"0000000000000000000000000000000000A:0\n{digest[5:].lower()}:42\n"
        return httpx.Response(200, text=body)

    checker = _online(handler)
    assert checker.is_breached(LEAKED)
    assert seen == [f"https://api.pwnedpasswords.com/range/{digest[:5]}"]
    assert LEAKED not in seen[0] and digest[5:] not in seen[0]
    assert not checker.is_breached("a much better passphrase here")


def test_online_padding_rows_and_outage_fail_open() -> None:
    digest = sha1_hex(LEAKED)
    padded = _online(lambda r: httpx.Response(200, text=f"{digest[5:]}:0\n"))
    assert not padded.is_breached(LEAKED)  # count 0 = padding, not a real breach
    down = _online(lambda r: httpx.Response(503))
    assert not down.is_breached(LEAKED)


def test_offline_and_off(tmp_path: Path) -> None:
    hashes = tmp_path / "pwned.txt"
    hashes.write_text(f"{sha1_hex(LEAKED).lower()}:9\n\nDEADBEEF\n")
    assert OfflineChecker(hashes).is_breached(LEAKED)
    assert not OfflineChecker(hashes).is_breached("another long secret")
    assert not NoCheck().is_breached(LEAKED)


def test_mode_selection(tmp_path: Path) -> None:
    assert isinstance(main._breach(Settings()), NoCheck)
    assert isinstance(main._breach(Settings(breach_check_mode="online")), OnlineChecker)
    hashes = tmp_path / "h.txt"
    hashes.write_text("")
    assert isinstance(
        main._breach(Settings(breach_check_mode="offline", breach_hash_file=str(hashes))),
        OfflineChecker,
    )
    with pytest.raises(RuntimeError, match="BREACH_HASH_FILE"):
        main._breach(Settings(breach_check_mode="offline"))


@pytest.mark.integration
def test_register_refuses_breached_password(make_client) -> None:  # type: ignore[no-untyped-def]
    c = make_client()

    class Leaked:
        def is_breached(self, password: str) -> bool:
            return password == LEAKED

    c.app.state.breach_checker = Leaked()
    bad = c.post("/api/v1/auth/register", json={"email": "leak@example.com", "password": LEAKED})
    assert bad.status_code == 400 and "known data breach" in bad.json()["error"]["message"]
    good = c.post("/api/v1/auth/register", json={"email": "leak@example.com", "password": PASSWORD})
    assert good.status_code == 201
