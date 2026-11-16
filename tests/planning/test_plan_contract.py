import pytest
from pydantic import ValidationError

from packages.contracts.plan import Limit


def test_limit_needs_a_bound() -> None:
    with pytest.raises(ValidationError, match="min, max or both"):
        Limit(name="length")


def test_limit_max_not_below_min() -> None:
    with pytest.raises(ValidationError, match="max must be >= min"):
        Limit(name="length", min=10, max=5)
