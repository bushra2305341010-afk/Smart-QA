import pytest

from packages.model_gateway.redact import redact


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        ("contact jane.doe+qa@example.com today", "email"),
        ("call +880 1712-345678 now", "phone"),
        ("call (555) 123-4567 now", "phone"),
        ("key sk-ant-api03-AbCdEf0123456789xyzXYZ0123 here", "api_key"),
        ("token ghp_abcdefghijklmnopqrstuvwxyz0123456789 here", "api_key"),
        ("Authorization: Bearer abc.def-ghi_jkl123456789", "bearer_token"),
        (
            "jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U ok",
            "jwt",
        ),
        ("card 4111 1111 1111 1111 used", "card"),
    ],
)
def test_sensitive_values_are_masked(raw: str, kind: str) -> None:
    result = redact(raw)
    assert f"[REDACTED:{kind}]" in result.text
    assert result.counts[kind] == 1


def test_non_luhn_digit_runs_are_not_cards() -> None:
    result = redact("order 1234 5678 9012 3456 shipped")
    assert "card" not in result.counts
    assert "1234 5678 9012 3456" in result.text


def test_secret_placeholders_are_preserved() -> None:
    text = "type {{secret:admin_password}} into the field"
    assert redact(text).text == text


def test_clean_text_unchanged_and_counts_empty() -> None:
    result = redact("Cards expiring in the current month must be accepted.")
    assert result.text == "Cards expiring in the current month must be accepted."
    assert result.counts == {}
    assert result.total == 0


def test_multiple_hits_are_counted() -> None:
    result = redact("a@x.io and b@y.io")
    assert result.counts == {"email": 2}
    assert result.total == 2
