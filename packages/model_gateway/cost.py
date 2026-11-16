"""Cost accounting and budget caps (F34). Budgets are checked before a call, never after."""

from __future__ import annotations

from dataclasses import dataclass

from packages.contracts.plan import PriceTable
from packages.model_gateway.types import Usage

_MTOK = 1_000_000
CACHE_WRITE_MULTIPLIER = 1.25
"""5-minute cache writes cost about 1.25x the input price."""


def usage_cost(usage: Usage, prices: PriceTable) -> float:
    """USD cost of `usage` at `prices`."""
    return (
        usage.input_tokens / _MTOK * prices.input_per_mtok_usd
        + usage.output_tokens / _MTOK * prices.output_per_mtok_usd
        + usage.cache_read_input_tokens / _MTOK * prices.cache_read_per_mtok_usd
        + usage.cache_creation_input_tokens
        / _MTOK
        * prices.input_per_mtok_usd
        * CACHE_WRITE_MULTIPLIER
    )


class BudgetExceededError(Exception):
    """A call would push spending over the cap (API code BUDGET_EXCEEDED)."""


@dataclass
class Budget:
    """Spending cap for a run or project. `cap_usd=None` means unlimited."""

    cap_usd: float | None
    spent_usd: float = 0.0

    def check(self, amount_usd: float) -> None:
        """Raise if spending `amount_usd` more would exceed the cap."""
        if self.cap_usd is not None and self.spent_usd + amount_usd > self.cap_usd:
            raise BudgetExceededError(
                f"budget cap ${self.cap_usd:.2f} would be exceeded "
                f"(spent ${self.spent_usd:.4f}, next call about ${amount_usd:.4f})"
            )

    def add(self, amount_usd: float) -> None:
        self.spent_usd += amount_usd

    @property
    def remaining(self) -> float | None:
        return None if self.cap_usd is None else self.cap_usd - self.spent_usd
