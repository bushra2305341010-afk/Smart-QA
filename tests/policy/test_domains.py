import pytest

from packages.policy.domains import allowed_hosts_for, is_allowed_url, split_host

BASE = "https://shop.test"


@pytest.mark.parametrize(
    ("url", "allowed", "expected"),
    [
        ("https://shop.test/cart", [], True),
        ("https://SHOP.TEST./cart", [], True),  # case + trailing dot
        ("http://shop.test", [], True),
        ("https://evil.test/", [], False),
        ("https://shop.test.evil.com/", [], False),  # look-alike suffix
        ("https://shop.test@evil.com/", [], False),  # user-info trick
        ("javascript:alert(1)", [], False),
        ("data:text/html,hi", [], False),
        ("file:///etc/passwd", [], False),
        ("ftp://shop.test/x", [], False),  # host ok, scheme not
        ("/relative/path", [], False),
        ("about:blank", [], True),
        ("https://cdn.example.com/a.js", ["cdn.example.com"], True),
        ("https://a.b.example.com/", ["*.example.com"], True),
        ("https://example.com/", ["*.example.com"], False),  # wildcard needs a subdomain
        ("http://localhost:8765/", ["localhost:8765"], True),
        ("http://localhost:9999/", ["localhost:8765"], False),
        ("http://localhost/", ["localhost:bad"], False),
        ("http://[::1]:99999/", [], False),  # invalid port
    ],
)
def test_is_allowed_url(url: str, allowed: list[str], expected: bool) -> None:
    assert is_allowed_url(url, BASE, allowed) is expected


def test_base_with_port_is_allowed_only_on_that_port() -> None:
    assert is_allowed_url("http://127.0.0.1:8765/x", "http://127.0.0.1:8765", [])
    assert not is_allowed_url("http://127.0.0.1:8000/x", "http://127.0.0.1:8765", [])


def test_bad_base_url_adds_nothing() -> None:
    assert allowed_hosts_for("not a url", ["a.test"]) == ["a.test"]
    assert not is_allowed_url("https://x.test/", "not a url", [])


def test_split_host() -> None:
    assert split_host("HTTPS://A.Test:8443/p") == ("https", "a.test", 8443)
    assert split_host("no-host") is None
