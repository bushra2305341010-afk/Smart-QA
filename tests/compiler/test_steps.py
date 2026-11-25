import pytest

from packages.compiler.steps import expected_action, parse_step
from packages.contracts.run import CompiledAction, Locator

ROUTES = {"cart": "/cart", "checkout": "/checkout"}


def one(text: str) -> CompiledAction:
    out = parse_step(text, 1, ROUTES)
    assert out is not None and len(out) == 1, text
    return out[0]


@pytest.mark.parametrize(
    ("text", "kind", "locator", "value"),
    [
        ("Go to /cart", "goto", None, "/cart"),
        ("1. Open https://shop.test/login.", "goto", None, "https://shop.test/login"),
        ("Navigate to the 'Checkout' page", "goto", None, "/checkout"),
        ("Visit the cart page", "goto", None, "/cart"),
        ("Enter 'a@example.com' in the 'Email' field", "fill", Locator(by="label", value="Email"),
         "a@example.com"),
        ('Type "{{secret:password}}" into "Password"', "fill",
         Locator(by="label", value="Password"), "{{secret:password}}"),
        ("Fill 'Quantity' with '3'", "fill", Locator(by="label", value="Quantity"), "3"),
        ("Select 'Dhaka' from the 'City' dropdown", "select", Locator(by="label", value="City"),
         "Dhaka"),
        ("Tick 'I agree' checkbox", "check", Locator(by="label", value="I agree"), None),
        ("Press Enter", "press", None, "Enter"),
        ("press the escape key", "press", None, "Escape"),
        ("Click 'Add to cart'", "click", Locator(by="role", role="button", value="Add to cart"),
         None),
        ("Click on the 'Home' link", "click", Locator(by="role", role="link", value="Home"), None),
        ("Tap \u201cMenu\u201d menu item", "click",
         Locator(by="role", role="menuitem", value="Menu"), None),
        ("Select \u2018Grades\u2019 tab", "click", Locator(by="role", role="tab", value="Grades"),
         None),
        ("Verify the URL contains '/orders'", "expect_url", None, "/orders"),
        ("Check that 'Saved' is shown", "expect_text", Locator(by="text", value="Saved"), None),
        ("Verify the error 'Name is required' is displayed", "expect_text",
         Locator(by="text", value="Name is required"), None),
        ("Expect 'Loading' is hidden", "expect_hidden", Locator(by="text", value="Loading"), None),
    ],
)  # fmt: skip
def test_grammar(text: str, kind: str, locator: Locator | None, value: str | None) -> None:
    a = one(text)
    assert (a.kind, a.locator, a.value) == (kind, locator, value)


@pytest.mark.parametrize(
    "text", ["Go to the unknown page", "Think about the product", "Click somewhere nice"]
)
def test_unparsed(text: str) -> None:
    assert parse_step(text, 1, ROUTES) is None
    assert parse_step(text, 1) is None


def test_expected_action() -> None:
    a = expected_action("Verify 'Order placed' is shown", 5)
    assert a is not None and a.expected and a.kind == "expect_text" and a.step_n == 5
    b = expected_action("The cart total shows 'Total: 10.00'.", 4)
    assert b is not None and b.locator == Locator(by="text", value="Total: 10.00") and b.expected
    c = expected_action("A \u201cWelcome back\u201d banner appears", 2)
    assert c is not None and c.locator is not None and c.locator.value == "Welcome back"
    assert expected_action("The order is saved", 3) is None
