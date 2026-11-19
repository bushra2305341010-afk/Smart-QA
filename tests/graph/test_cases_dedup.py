from packages.cases.dedup import code_prefix, dedupe, next_codes
from packages.contracts.case import DesignedCase, DesignedStep


def case(role: str, steps: list[str], expected: str) -> DesignedCase:
    return DesignedCase(
        title="t", role=role, technique="happy_path", steps=[DesignedStep(action=a) for a in steps],
        expected_text=expected, source="S1", quote="q",
    )  # fmt: skip


def test_dedupe_by_role_steps_expected() -> None:
    a = case("Customer", ["Open cart", "Pay"], "Order is placed.")
    b = case("customer", ["open cart!", "pay"], "order is placed")
    c = case("Admin", ["Open cart", "Pay"], "Order is placed.")
    unique, dropped = dedupe([a, b, c])
    assert unique == [a, c] and dropped == 1


def test_codes() -> None:
    assert code_prefix("Sign up") == "TC-SIG" and code_prefix("2FA") == "TC-2FA"
    assert code_prefix("!!") == "TC-GEN"
    assert next_codes("TC-SIG", ["TC-SIG-002", "TC-SIG-010", "TC-CHK-099", "TC-SIG-x"], 2) == [
        "TC-SIG-011",
        "TC-SIG-012",
    ]
    assert next_codes("TC-NEW", [], 1) == ["TC-NEW-001"]
