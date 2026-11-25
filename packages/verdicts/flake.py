"""Flake features (F22). A pass on retry is Flaky only with noise evidence (sector 06 bug locator:
"Real bug labelled Flaky → require noise evidence, not just pass-on-retry")."""

from __future__ import annotations

import re
from dataclasses import dataclass

from packages.contracts.run import AttemptResult

# A retry slower/faster than this ratio is timing noise.
TIMING_RATIO = 2.0
TRANSIENT_HTTP = frozenset({408, 425, 429, 500, 502, 503, 504})
_VOLATILE = re.compile(r"\b(?:0x[0-9a-f]+|[0-9a-f]{8,}|\d+(?:\.\d+)?)(?:ms|s)?\b", re.IGNORECASE)


def signature(result: AttemptResult) -> tuple[str, int | None, str] | None:
    """Failure identity with volatile numbers/ids removed, so two runs compare equal."""
    if result.failure is None:
        return None
    message = _VOLATILE.sub("#", result.failure.message.lower()).strip()
    return result.failure.kind, result.failure.step_n, message


@dataclass(frozen=True)
class FlakeFeatures:
    timing_noise: bool
    network_noise: bool
    console_noise: bool
    same_signature: bool

    @property
    def noisy(self) -> bool:
        return self.timing_noise or self.network_noise or self.console_noise


def features(first: AttemptResult, rerun: AttemptResult) -> FlakeFeatures:
    a, b = max(first.duration_ms, 1), max(rerun.duration_ms, 1)
    timing = (
        first.status == "timed_out"
        or (first.failure is not None and first.failure.kind == "timeout")
        or max(a, b) / min(a, b) >= TIMING_RATIO
    )
    network = (
        first.network_errors > rerun.network_errors
        or (first.failure is not None and first.failure.kind == "network")
        or (first.http_status in TRANSIENT_HTTP and rerun.http_status not in TRANSIENT_HTTP)
    )
    console = first.console_errors > rerun.console_errors
    same = signature(first) is not None and signature(first) == signature(rerun)
    return FlakeFeatures(timing, network, console, same)
