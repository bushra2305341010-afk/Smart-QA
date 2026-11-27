"""Policy hook (sector 05, N18): every browser action and request goes through
`packages.policy.check` before it happens. A blocked action is never performed.

Element facts (text, aria-label, title, link target, "inside a card form") are read from the
live element right before acting, so a page cannot hide a Delete button behind a harmless
plan step: the policy judges what would actually be clicked.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.policy.actions import Action, ActionKind, Decision, PolicyContext, check

ELEMENT_FACTS_JS = """el => {
  const form = el.closest('form');
  const card = !!(form && form.querySelector(
    'input[autocomplete^="cc-"], input[name*="card" i], input[id*="card" i]'));
  const link = el.closest('a');
  return {
    text: ((el.innerText || el.value || '') + '').trim().slice(0, 200),
    aria: el.getAttribute('aria-label'),
    title: el.getAttribute('title'),
    href: link ? link.href : null,
    card: card,
  };
}"""
FOCUSED_FACTS_JS = (
    "() => { const el = document.activeElement; if (!el || el === document.body) return null;"
    " return (" + ELEMENT_FACTS_JS + ")(el); }"
)
REPO_FIXTURES = Path(__file__).resolve().parents[2] / "evals" / "fixtures"


def policy_context(
    env: dict[str, Any], fixtures_root: Path | None = REPO_FIXTURES
) -> PolicyContext:
    return PolicyContext(
        env_kind=str(env.get("kind", "local")),
        base_url=str(env["base_url"]),
        allowed_hosts=list(env.get("allowed_hosts", [])),
        safe_actions=dict(env.get("safe_actions", {})),
        fixtures_root=fixtures_root,
    )


def element_action(
    kind: ActionKind, facts: dict[str, Any] | None, name: str | None, value: str | None = None
) -> Action:
    facts = facts or {}
    href = facts.get("href") or None
    if kind != "click" or (href and href.lower().startswith(("javascript:", "#"))):
        href = None  # in-page handlers are judged by their text, not a fake URL
    return Action(
        kind=kind,
        text=facts.get("text") or None,
        aria_label=facts.get("aria") or None,
        title=facts.get("title") or None,
        url=href,
        name=name,
        value=value,
        in_payment_form=bool(facts.get("card")),
    )


@dataclass
class RequestGuard:
    """Route handler: aborts blocked requests. A blocked navigation or a blocked write request
    (POST/PUT/PATCH/DELETE) marks the attempt Blocked; a blocked third-party GET (analytics,
    fonts) is aborted silently and does not stop the test."""

    ctx: PolicyContext
    blocked: Decision | None = None
    aborted: int = 0

    def decide(self, method: str, url: str, is_navigation: bool) -> Decision:
        kind: ActionKind = "navigate" if is_navigation else "request"
        decision = check(Action(kind=kind, url=url, method=method), self.ctx)
        if not decision.allowed:
            self.aborted += 1
            if (is_navigation or method.upper() not in {"GET", "HEAD", "OPTIONS"}) and (
                self.blocked is None
            ):
                self.blocked = decision
        return decision

    def handle(self, route: Any) -> None:
        req = route.request
        if req.url.startswith(("data:", "blob:")):
            route.continue_()
            return
        decision = self.decide(req.method, req.url, req.is_navigation_request())
        if decision.allowed:
            route.continue_()
        else:
            route.abort("blockedbyclient")
