"""Deterministic step grammar (F20): designed step text → typed `CompiledAction`s.

The grammar covers the phrasing the Designer is asked to use ("Click 'Add to cart'", "Enter
'a@example.com' in 'Email'", "Go to /cart", "Verify the text 'Total: 10.00' is shown"). Steps it
cannot map are returned as unparsed; the compiler worker may ask the model for those only.
Quoted values accept '...', "..." and curly quotes. Matching ignores case for the verbs only.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from packages.contracts.run import CompiledAction, Locator

Q = r"""(?:'(?P<{n}>[^']+)'|"(?P<{n}2>[^"]+)"|\u201c(?P<{n}3>[^\u201d]+)\u201d|\u2018(?P<{n}4>[^\u2019]+)\u2019)"""  # noqa: E501


def _q(name: str) -> str:
    return Q.format(n=name)


def _val(m: re.Match[str], name: str) -> str:
    for suffix in ("", "2", "3", "4"):
        v = m.group(name + suffix)
        if v is not None:
            return v
    raise KeyError(name)  # pragma: no cover - every pattern using _q has the group


ART = r"(?:the\s+)?"
KIND = r"(?:\s+(?P<kind>button|link|tab|checkbox|menu\s*item|option))?"
FIELD = r"(?:\s+(?:field|box|input|textbox))?"
URLISH = r"(?P<url>(?:https?://|/)\S*)"

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("goto", re.compile(rf"^(?:go\s+to|open|navigate\s+to|visit)\s+{ART}(?:{URLISH}|{_q('page')}|(?P<name>.+?))(?:\s+page)?$", re.I)),  # noqa: E501
    ("fill", re.compile(rf"^(?:enter|type|input|fill\s+in|fill)\s+{_q('value')}\s+(?:in|into|as)\s+{ART}{_q('field')}{FIELD}$", re.I)),  # noqa: E501
    ("fill", re.compile(rf"^(?:fill|set)\s+{ART}{_q('field')}{FIELD}\s+(?:with|to)\s+{_q('value')}$", re.I)),  # noqa: E501
    ("select", re.compile(rf"^(?:select|choose|pick)\s+{_q('value')}\s+(?:from|in)\s+{ART}{_q('field')}(?:\s+(?:dropdown|list|menu|select))?$", re.I)),  # noqa: E501
    ("check", re.compile(rf"^(?:check|tick|enable)\s+{ART}{_q('field')}(?:\s+checkbox)?$", re.I)),
    ("press", re.compile(r"^press\s+(?:the\s+)?(?P<key>enter|tab|escape|space)(?:\s+key)?$", re.I)),
    ("click", re.compile(rf"^(?:click|press|tap|select|choose)\s+(?:on\s+)?{ART}{_q('name')}{KIND}$", re.I)),  # noqa: E501
    ("expect_url", re.compile(rf"^(?:verify|check|expect|confirm)\s+(?:that\s+)?{ART}(?:url|address)\s+(?:is|contains|includes)\s+{_q('value')}$", re.I)),  # noqa: E501
    ("expect_hidden", re.compile(rf"^(?:verify|check|expect|confirm)\s+(?:that\s+)?{ART}(?:text\s+|message\s+)?{_q('value')}\s+is\s+(?:not\s+shown|not\s+displayed|hidden|gone)$", re.I)),  # noqa: E501
    ("expect_text", re.compile(rf"^(?:verify|check|expect|confirm|see)\s+(?:that\s+)?{ART}(?:text\s+|message\s+|error\s+)?{_q('value')}(?:\s+(?:is|appears|shows|is\s+shown|is\s+displayed|is\s+visible))*(?:\s+(?:shown|displayed|visible))?$", re.I)),  # noqa: E501
]  # fmt: skip
KEYS = {"enter": "Enter", "tab": "Tab", "escape": "Escape", "space": " "}
ROLES = {"button": "button", "link": "link", "tab": "tab", "checkbox": "checkbox",
         "option": "option"}  # fmt: skip


def _clean(text: str) -> str:
    text = re.sub(r"^\s*(?:step\s*)?\d+[.)]\s*", "", text.strip(), flags=re.I)
    return text.rstrip(" .;")


def _route(name: str, routes: Mapping[str, str]) -> str | None:
    key = re.sub(r"\s+page$", "", name.strip().lower())
    return routes.get(key)


def parse_step(
    text: str, step_n: int, routes: Mapping[str, str] | None = None
) -> list[CompiledAction] | None:
    """Actions for one designed step, or None if the grammar does not cover it."""
    routes = routes or {}
    line = _clean(text)
    for kind, pattern in PATTERNS:
        m = pattern.match(line)
        if not m:
            continue
        if kind == "goto":
            url = m.group("url") or _route(
                m.group("page") or m.group("page2") or m.group("page3") or m.group("page4")
                or m.group("name") or "", routes,
            )  # fmt: skip
            if url is None:
                return None
            return [CompiledAction(kind="goto", step_n=step_n, value=url)]
        if kind in {"fill", "select"}:
            loc = Locator(by="label", value=_val(m, "field"))
            return [CompiledAction(kind=kind, step_n=step_n, locator=loc, value=_val(m, "value"))]
        if kind == "check":
            loc = Locator(by="label", value=_val(m, "field"))
            return [CompiledAction(kind="check", step_n=step_n, locator=loc)]
        if kind == "press":
            return [CompiledAction(kind="press", step_n=step_n, value=KEYS[m.group("key").lower()])]
        if kind == "click":
            word = (m.group("kind") or "button").lower().replace(" ", "")
            role = "menuitem" if word == "menuitem" else ROLES[word]
            loc = Locator(by="role", role=role, value=_val(m, "name"))
            return [CompiledAction(kind="click", step_n=step_n, locator=loc)]
        if kind == "expect_url":
            return [CompiledAction(kind="expect_url", step_n=step_n, value=_val(m, "value"))]
        loc = Locator(by="text", value=_val(m, "value"))
        return [CompiledAction(kind=kind, step_n=step_n, locator=loc)]
    return None


QUOTED = re.compile(r"'([^']{2,})'|\"([^\"]{2,})\"|\u201c([^\u201d]{2,})\u201d")


def expected_action(expected_text: str, step_n: int) -> CompiledAction | None:
    """The check for the cited expected result: a quoted literal must be visible on the page.

    If the expected result names no literal text, there is nothing deterministic to check and
    the compiler leaves it to the model (or the case ends with no checked expectation, which the
    Judge reports as Unable to Verify, never Pass).
    """
    parsed = parse_step(expected_text, step_n)
    if parsed and parsed[0].kind in {"expect_text", "expect_url", "expect_hidden"}:
        return parsed[0].model_copy(update={"expected": True})
    m = QUOTED.search(expected_text)
    if not m:
        return None
    literal = next(g for g in m.groups() if g)
    return CompiledAction(
        kind="expect_text", step_n=step_n, locator=Locator(by="text", value=literal), expected=True
    )
