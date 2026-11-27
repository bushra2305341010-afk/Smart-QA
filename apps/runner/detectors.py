"""Blocked detectors (N19): pages the runner must not try to get past.

A CAPTCHA, a one-time-code prompt, a bot wall or an unexpected login wall means the product could
not be tested, not that it failed, so the Judge reports Blocked. Detection is signature-based
over the page's text, frame URLs and form fields; the page text is data, never instructions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from packages.contracts.run import BlockedSignal

CAPTCHA_FRAMES = re.compile(
    r"(?:google\.com/recaptcha|recaptcha\.net|hcaptcha\.com|challenges\.cloudflare\.com"
    r"|turnstile|arkoselabs\.com|funcaptcha)",
    re.IGNORECASE,
)
CAPTCHA_TEXT = re.compile(
    r"\b(?:captcha|i'?m not a robot|verify (?:that )?you are (?:a )?human|select all images)\b",
    re.IGNORECASE,
)
BOT_WALL_TEXT = re.compile(
    r"(?:checking your browser|attention required|access denied|unusual traffic"
    r"|request blocked|are you a robot)",
    re.IGNORECASE,
)
MFA_TEXT = re.compile(
    r"(?:one[- ]time (?:code|password)|verification code|authenticator app|enter the \d-digit"
    r"|two[- ]factor|2fa code|we (?:sent|texted) (?:you )?a code)",
    re.IGNORECASE,
)
LOGIN_TEXT = re.compile(r"\b(?:sign in|log in|login)\b", re.IGNORECASE)


@dataclass(frozen=True)
class PageSnapshot:
    url: str
    title: str = ""
    text: str = ""  # visible text (truncated by the caller)
    frame_urls: list[str] = field(default_factory=list)
    has_otp_input: bool = False  # input[autocomplete=one-time-code]
    has_password_input: bool = False
    status: int | None = None


@dataclass(frozen=True)
class Detection:
    signal: BlockedSignal
    reason: str


def detect(page: PageSnapshot, *, expect_login: bool = False) -> Detection | None:
    if any(CAPTCHA_FRAMES.search(u) for u in page.frame_urls) or CAPTCHA_TEXT.search(page.text):
        return Detection("captcha", "A CAPTCHA is shown")
    if page.status in (403, 429, 503) and BOT_WALL_TEXT.search(f"{page.title} {page.text}"):
        return Detection("bot_wall", f"Bot protection page (HTTP {page.status})")
    if page.has_otp_input or MFA_TEXT.search(page.text):
        return Detection("mfa", "A one-time code / second factor is requested")
    if (
        not expect_login
        and page.has_password_input
        and LOGIN_TEXT.search(f"{page.title} {page.text}")
        and re.search(r"/(?:login|signin|sign-in|auth)\b", page.url, re.IGNORECASE)
    ):
        return Detection("login_wall", "Redirected to a login page")
    return None


def env_down(status: int | None, error: str | None) -> Detection | None:
    """The target itself is unreachable (connection refused, DNS, 502/503/504 on navigation)."""
    if error and re.search(r"ERR_CONNECTION|ERR_NAME_NOT_RESOLVED|ECONNREFUSED|ERR_ADDRESS", error):
        return Detection("env_down", "The test environment is unreachable")
    if status in (502, 503, 504):
        return Detection("env_down", f"The test environment answered HTTP {status}")
    return None
