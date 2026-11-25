"""Safe-action policy (docs/09-security.md §6, N18). Code, not a prompt: 100% branch coverage.

The runner calls `check(action, ctx)` before every browser action and every request it makes.
A blocked action is never performed; the case gets the Blocked verdict with the policy reason.

Defaults (an environment can relax only what the table says it can):

| Category  | Default | Relaxed by                                  |
|-----------|---------|---------------------------------------------|
| production| block   | `safe_actions.allow_production: true`       |
| delete    | block   | `safe_actions.allow: ["delete"]`            |
| payment   | block   | `safe_actions.payments: "test"` (test cards only) |
| transfer  | block   | never                                       |
| messaging | block   | `safe_actions.mail_sink: true`              |
| off_domain| block   | add the host to `allowed_hosts`             |
| upload    | block   | only files inside the fixtures folder       |

Text matching is case-insensitive and looks at every name the element exposes (visible text,
aria-label, accessible name, title), so a button whose text hides the intent behind an icon is
still caught by its aria-label.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from packages.policy.domains import is_allowed_url, split_host

ActionKind = Literal["navigate", "click", "fill", "select", "check", "press", "upload", "request"]
Category = Literal[
    "production", "delete", "payment", "transfer", "messaging", "off_domain", "upload"
]
INTERACTIONS = frozenset({"click", "check", "select", "press"})
READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _words(*phrases: str) -> re.Pattern[str]:
    alternatives = "|".join(p.replace(" ", r"[\s_-]+") for p in phrases)
    return re.compile(rf"(?<![a-z0-9])(?:{alternatives})(?![a-z0-9])", re.IGNORECASE)


# Intent keywords on interactive elements (button text, aria-label, accessible name, title).
DELETE_WORDS = _words(
    "delete", "remove", "destroy", "erase", "purge", "wipe", "close account",
    "deactivate account", "terminate account", "delete account",
)  # fmt: skip
PAYMENT_WORDS = _words(
    "pay", "pay now", "place order", "buy now", "purchase", "complete order", "submit payment",
    "confirm payment", "checkout now", "complete purchase",
)  # fmt: skip
TRANSFER_WORDS = _words(
    "transfer", "wire", "send money", "withdraw", "payout", "remit", "move funds",
)  # fmt: skip
MESSAGING_WORDS = _words(
    "send email", "send e-mail", "send sms", "send text", "send message", "send invite",
    "send invitation", "invite", "email parents", "email all", "notify", "broadcast",
    "send newsletter", "text message",
)  # fmt: skip

# Route patterns (path segments) for links and requests.
DELETE_ROUTES = re.compile(r"/(?:delete|remove|destroy|purge)(?:[/?#._-]|$)", re.IGNORECASE)
PAYMENT_ROUTES = re.compile(r"/(?:pay|payment|payments|charge|charges)(?:[/?#._-]|$)", re.I)
TRANSFER_ROUTES = re.compile(r"/(?:transfer|transfers|withdraw|payout|payouts)(?:[/?#._-]|$)", re.I)
MESSAGING_ROUTES = re.compile(
    r"/(?:email|emails|mail|sms|invite|invites|invitations|notify|notifications|send)(?:[/?#._-]|$)",
    re.IGNORECASE,
)

# Payment service providers: a request or navigation to one is a payment action.
PSP_HOSTS = (
    "stripe.com", "paypal.com", "braintreegateway.com", "adyen.com", "squareup.com",
    "razorpay.com", "sslcommerz.com", "bkash.com", "checkout.com", "klarna.com",
)  # fmt: skip
# Published test card numbers (Stripe, Adyen, Braintree docs); any other Luhn-valid number
# typed into a field is treated as a real card and blocked even in payments=test mode.
TEST_CARDS = frozenset(
    {
        "4242424242424242", "4000056655665556", "5555555555554444", "2223003122003222",
        "5200828282828210", "378282246310005", "371449635398431", "6011111111111117",
        "3056930009020004", "36227206271667", "3566002020360505", "6200000000000005",
        "4111111111111111", "4000000000000002", "4000000000009995", "4000002500003155",
    }
)  # fmt: skip
CARD_LIKE = re.compile(r"^[\d\s-]{13,23}$")


@dataclass(frozen=True)
class Action:
    """One thing the runner is about to do. Names come from the element, not from the plan."""

    kind: ActionKind
    url: str | None = None  # navigate / request target, or the link's href for a click
    text: str | None = None  # visible text of the element
    aria_label: str | None = None
    name: str | None = None  # accessible name used by the locator
    title: str | None = None
    method: str | None = None  # HTTP method for `request`
    value: str | None = None  # typed / selected value
    file_path: str | None = None  # for `upload`
    in_payment_form: bool = False  # the element sits in a form with card fields

    def labels(self) -> list[str]:
        return [x for x in (self.text, self.aria_label, self.name, self.title) if x]


@dataclass(frozen=True)
class PolicyContext:
    env_kind: str  # local | staging | public | production
    base_url: str
    allowed_hosts: list[str] = field(default_factory=list)
    safe_actions: Mapping[str, Any] = field(default_factory=dict)
    fixtures_root: Path | None = None

    @property
    def relaxed(self) -> frozenset[str]:
        allow = self.safe_actions.get("allow", [])
        return frozenset(str(x).lower() for x in allow) if isinstance(allow, list) else frozenset()


@dataclass(frozen=True)
class Decision:
    allowed: bool
    category: Category | None = None
    reason: str = ""

    @property
    def rule(self) -> str:
        return f"policy.{self.category}" if self.category else "policy.allowed"


ALLOW = Decision(True)


def _block(category: Category, reason: str) -> Decision:
    return Decision(False, category, reason)


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def looks_like_real_card(value: str) -> bool:
    if not CARD_LIKE.match(value.strip()):
        return False
    digits = re.sub(r"\D", "", value)
    return 13 <= len(digits) <= 19 and _luhn(digits) and digits not in TEST_CARDS


def _is_psp(url: str) -> bool:
    parsed = split_host(url)
    if parsed is None:
        return False
    host = parsed[1]
    return any(host == p or host.endswith("." + p) for p in PSP_HOSTS)


def _label_category(action: Action) -> Category | None:
    labels = action.labels()
    for words, category in (
        (TRANSFER_WORDS, "transfer"),
        (PAYMENT_WORDS, "payment"),
        (MESSAGING_WORDS, "messaging"),
        (DELETE_WORDS, "delete"),
    ):
        if any(words.search(label) for label in labels):
            return category  # type: ignore[return-value]
    return None


def _route_category(url: str) -> Category | None:
    if _is_psp(url):
        return "payment"
    path = url.split("://", 1)[-1]
    path = path[path.find("/") :] if "/" in path else ""
    for routes, category in (
        (TRANSFER_ROUTES, "transfer"),
        (PAYMENT_ROUTES, "payment"),
        (MESSAGING_ROUTES, "messaging"),
        (DELETE_ROUTES, "delete"),
    ):
        if routes.search(path):
            return category  # type: ignore[return-value]
    return None


def _category_of(action: Action) -> Category | None:
    if action.kind == "request":
        method = (action.method or "GET").upper()
        if method == "DELETE":
            return "delete"
        if method in READ_METHODS:
            return "payment" if action.url and _is_psp(action.url) else None
        return _route_category(action.url) if action.url else None
    if action.kind == "navigate":
        return _route_category(action.url) if action.url else None
    if action.kind in INTERACTIONS:
        found = _label_category(action)
        if found is None and action.in_payment_form and action.kind in {"click", "press"}:
            return "payment"
        if found is None and action.url:  # a link's href
            return _route_category(action.url)
        return found
    return None


def _relaxed_ok(category: Category, ctx: PolicyContext) -> Decision:
    """Apply the environment's explicit relaxations; transfer can never be relaxed."""
    if category == "delete" and "delete" in ctx.relaxed:
        return ALLOW
    if category == "payment" and ctx.safe_actions.get("payments") == "test":
        return ALLOW
    if category == "messaging" and ctx.safe_actions.get("mail_sink") is True:
        return ALLOW
    reasons = {
        "delete": "Destructive action (delete/remove) is blocked by the safe-action policy",
        "payment": "Payment actions are blocked unless the environment uses test payments",
        "transfer": "Money transfers are always blocked",
        "messaging": "Sending email/SMS/invites is blocked unless the environment has a mail sink",
    }
    return _block(category, reasons[category])


def _check_upload(action: Action, ctx: PolicyContext) -> Decision:
    if not action.file_path or ctx.fixtures_root is None:
        return _block("upload", "File upload is allowed only for files from the fixtures folder")
    root = ctx.fixtures_root.resolve()
    target = (root / action.file_path).resolve()
    if target != root and root in target.parents and target.is_file():
        return ALLOW
    return _block("upload", "File upload is allowed only for files from the fixtures folder")


def check(action: Action, ctx: PolicyContext) -> Decision:
    """Allow or block one action. Order matters: environment, domain, then intent."""
    if ctx.env_kind == "production" and ctx.safe_actions.get("allow_production") is not True:
        return _block("production", "The target is a production environment; tests are blocked")

    if action.kind in {"navigate", "request"} or (action.kind == "click" and action.url):
        if action.url is None:
            return _block("off_domain", "Navigation without a URL is not allowed")
        if not is_allowed_url(action.url, ctx.base_url, ctx.allowed_hosts):
            return _block("off_domain", "The URL's host is not in the environment's allowed hosts")

    if action.kind == "upload":
        return _check_upload(action, ctx)

    if action.kind == "fill" and action.value and looks_like_real_card(action.value):
        return _block("payment", "A real-looking card number may never be typed; use a test card")

    category = _category_of(action)
    if category is None:
        return ALLOW
    return _relaxed_ok(category, ctx)
