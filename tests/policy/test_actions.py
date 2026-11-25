"""Every row of docs/09-security.md §6, allowed/blocked, plus environment rules."""

from pathlib import Path
from typing import Any

import pytest

from packages.policy.actions import (
    Action,
    Decision,
    PolicyContext,
    check,
    looks_like_real_card,
)

FIXTURES = Path(__file__).resolve().parents[2] / "evals" / "fixtures"


def ctx(kind: str = "staging", **safe: Any) -> PolicyContext:
    return PolicyContext(
        env_kind=kind,
        base_url="https://shop.test",
        allowed_hosts=["checkout.stripe.com"],
        safe_actions=safe,
        fixtures_root=FIXTURES,
    )


def click(text: str | None = None, **kw: Any) -> Action:
    return Action(kind="click", text=text, **kw)


BLOCKED_BY_DEFAULT = [
    # delete / remove / close account: text, aria-label, accessible name, title, route, DELETE
    (click("Delete student"), "delete"),
    (click("REMOVE"), "delete"),
    (click(aria_label="Close account"), "delete"),
    (click(name="delete-account"), "delete"),
    (click(title="Wipe data"), "delete"),
    (Action(kind="navigate", url="https://shop.test/students/4/delete"), "delete"),
    (click("Go", url="https://shop.test/items/remove?id=1"), "delete"),
    (Action(kind="request", method="DELETE", url="https://shop.test/api/students/4"), "delete"),
    (Action(kind="request", method="post", url="https://shop.test/api/destroy"), "delete"),
    # pay / checkout submit
    (click("Pay now"), "payment"),
    (click("Place order"), "payment"),
    (Action(kind="press", text="Continue", in_payment_form=True), "payment"),
    (click("Submit", in_payment_form=True), "payment"),
    (Action(kind="request", method="POST", url="https://shop.test/api/payments"), "payment"),
    (Action(kind="request", method="GET", url="https://checkout.stripe.com/c/1"), "payment"),
    (Action(kind="navigate", url="https://checkout.stripe.com/pay/1"), "payment"),
    # transfer money
    (click("Transfer funds"), "transfer"),
    (click(aria_label="Send money"), "transfer"),
    (Action(kind="request", method="POST", url="https://shop.test/api/transfers"), "transfer"),
    # send email / SMS / invite
    (click("Email parents"), "messaging"),
    (click("Send SMS"), "messaging"),
    (click(aria_label="Invite"), "messaging"),
    (Action(kind="request", method="PUT", url="https://shop.test/api/notify"), "messaging"),
    # off-domain navigation
    (Action(kind="navigate", url="https://evil.test/"), "off_domain"),
    (Action(kind="navigate"), "off_domain"),
    (click("Docs", url="https://other.test/docs"), "off_domain"),
    (Action(kind="request", method="GET", url="https://tracker.evil/x"), "off_domain"),
    # file upload
    (Action(kind="upload", file_path="../../etc/passwd"), "upload"),
    (Action(kind="upload", file_path="missing.txt"), "upload"),
    (Action(kind="upload", file_path="."), "upload"),
    (Action(kind="upload"), "upload"),
]


@pytest.mark.parametrize(("action", "category"), BLOCKED_BY_DEFAULT)
def test_blocked_by_default(action: Action, category: str) -> None:
    decision = check(action, ctx())
    assert decision == Decision(False, category, decision.reason)  # type: ignore[arg-type]
    assert decision.reason
    assert decision.rule == f"policy.{category}"


ALLOWED = [
    click("Add to cart"),
    click("Save"),
    click("Payment history"),  # a noun on a link, not the pay verb
    click("Removed items"),  # word boundary: "removed" is not "remove"
    click(),
    Action(kind="fill", name="Email", value="a@example.com"),
    Action(kind="fill", name="Card number", value="4242 4242 4242 4242"),  # test card
    Action(kind="fill", name="Phone", value="1234567890123"),  # not Luhn-valid
    Action(kind="select", name="Country", value="BD"),
    Action(kind="check", name="I agree"),
    Action(kind="navigate", url="https://shop.test/cart"),
    Action(kind="navigate", url="https://shop.test"),
    Action(kind="request", method="GET", url="https://shop.test/api/payments"),
    Action(kind="request", url="https://shop.test/api/items"),
    Action(kind="request", method="POST", url="https://shop.test/api/items"),
    Action(kind="upload", file_path="sample.txt"),
    click("Next", url="https://shop.test/page/2"),
]


@pytest.mark.parametrize("action", ALLOWED)
def test_allowed_by_default(action: Action) -> None:
    assert check(action, ctx()).allowed


def test_real_card_blocked_even_in_test_payment_mode() -> None:
    action = Action(kind="fill", name="Card number", value="4539 1488 0343 6467")
    decision = check(action, ctx(payments="test"))
    assert not decision.allowed and decision.category == "payment"


@pytest.mark.parametrize(
    ("action", "safe"),
    [
        (click("Delete student"), {"allow": ["Delete"]}),
        (click("Pay now"), {"payments": "test"}),
        (click("Email parents"), {"mail_sink": True}),
    ],
)
def test_environment_can_relax(action: Action, safe: dict[str, Any]) -> None:
    assert not check(action, ctx()).allowed
    assert check(action, ctx(**safe)).allowed


@pytest.mark.parametrize(
    "safe",
    [
        {"allow": ["transfer"], "payments": "test", "mail_sink": True},
        {"allow": "transfer"},  # malformed: not a list
    ],
)
def test_transfer_can_never_be_relaxed(safe: dict[str, Any]) -> None:
    assert not check(click("Wire money"), ctx(**safe)).allowed


def test_relaxations_need_exact_values() -> None:
    assert not check(click("Email parents"), ctx(mail_sink="yes")).allowed
    assert not check(click("Pay now"), ctx(payments="live")).allowed


def test_production_blocks_everything_by_default() -> None:
    decision = check(click("Add to cart"), ctx("production"))
    assert not decision.allowed and decision.category == "production"
    assert not check(click("Add to cart"), ctx("production", allow_production="true")).allowed


def test_production_opt_in_still_applies_other_rules() -> None:
    prod = ctx("production", allow_production=True)
    assert check(click("Add to cart"), prod).allowed
    assert not check(click("Delete"), prod).allowed


def test_upload_without_fixtures_root_is_blocked() -> None:
    c = PolicyContext(env_kind="local", base_url="http://localhost:8765")
    assert not check(Action(kind="upload", file_path="sample.txt"), c).allowed


def test_allowed_decision_rule() -> None:
    assert check(click("Save"), ctx()).rule == "policy.allowed"


@pytest.mark.parametrize(
    ("value", "real"),
    [
        ("4539 1488 0343 6467", True),
        ("4539-1488-0343-6467", True),
        ("4242424242424242", False),
        ("4539148803436468", False),  # Luhn fails
        ("abcd", False),
        ("123456789012", False),  # too short
    ],
)
def test_looks_like_real_card(value: str, real: bool) -> None:
    assert looks_like_real_card(value) is real


def test_unparsable_url_is_not_a_psp() -> None:
    from packages.policy.actions import _is_psp

    assert not _is_psp("not a url")
    assert _is_psp("https://api.stripe.com/v1/charges")
