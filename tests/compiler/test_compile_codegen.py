import ast

import pytest

from packages.compiler.codegen import ImportNotAllowedError, check_imports, render, secret_env
from packages.compiler.compile import NotCompilableError, compile_case, merge
from packages.contracts.run import CompiledAction, CompiledCase, Locator

STEPS = [
    (1, "Go to /login"),
    (2, "Enter '{{secret:email}}' in 'Email'"),
    (3, "Enter 'not-a-secret' in 'Note'"),
    (4, "Click 'Sign in'"),
    (5, "Wiggle the mouse"),
]


def test_compile_case_marks_unparsed_and_expected() -> None:
    case = compile_case("c1", "TC-SIG-001", STEPS, "The page shows 'Welcome'")
    assert [a.kind for a in case.actions] == ["goto", "fill", "fill", "click", "expect_text"]
    assert case.unparsed_steps == [5]
    assert case.actions[-1].expected and case.actions[-1].step_n == 6


def test_last_step_check_becomes_expected() -> None:
    case = compile_case("c1", "X", [(1, "Go to /"), (2, "Verify 'Hi' is shown")], "Greeting")
    assert case.actions[-1].expected and case.unparsed_steps == []


def test_no_expected_leaves_a_slot_for_the_model() -> None:
    case = compile_case("c1", "X", [(1, "Go to /")], "The order is saved")
    assert case.unparsed_steps == [2] and not any(a.expected for a in case.actions)


def test_start_url_inserted_only_when_missing() -> None:
    case = compile_case("c1", "X", [(1, "Click 'A'")], "'B'", start_url="/")
    assert case.actions[0].kind == "goto"
    case = compile_case("c1", "X", [(1, "Go to /x")], "'B'", start_url="/")
    assert [a.value for a in case.actions if a.kind == "goto"] == ["/x"]


def test_nothing_compilable() -> None:
    with pytest.raises(NotCompilableError):
        compile_case("c1", "X", [(1, "Dance")], "Nothing literal")


def test_merge_only_fills_unparsed_steps() -> None:
    case = compile_case("c1", "X", STEPS, "'Welcome'")
    filled = [
        CompiledAction(kind="press", step_n=5, value="Tab", expected=True),
        CompiledAction(kind="click", step_n=4, locator=Locator(by="css", value="#evil")),
    ]
    out = merge(case, filled)
    assert out.unparsed_steps == []
    step5 = [a for a in out.actions if a.step_n == 5]
    assert step5 == [CompiledAction(kind="press", step_n=5, value="Tab")]  # expected stripped
    assert [a for a in out.actions if a.step_n == 4] == [a for a in case.actions if a.step_n == 4]


def test_merge_may_supply_missing_expected() -> None:
    case = compile_case("c1", "X", [(1, "Go to /")], "The order is saved")
    check = CompiledAction(
        kind="expect_text", step_n=2, locator=Locator(by="text", value="Saved"), expected=True
    )
    assert merge(case, [check]).actions[-1].expected


def test_render_is_valid_python_with_secrets_from_env() -> None:
    case = compile_case("c1", "TC-SIG-001", STEPS, "The page shows 'Welcome'")
    src = render(case, "https://shop.test/", "The page shows 'Welcome'", 'It says """hi"""')
    ast.parse(src)
    assert "os.environ['SAQ_SECRET_EMAIL']" in src
    assert "fill('not-a-secret')" in src
    assert "def test_tc_sig_001(page: Page)" in src
    assert "BASE_URL + '/login'" in src
    assert "# step 5: not compiled" in src
    assert "# expected result (cited)" in src
    assert secret_env("email") == "SAQ_SECRET_EMAIL"


def test_render_every_action_kind() -> None:
    def loc(by: str) -> Locator:
        return Locator(by=by, value="v")

    actions = [
        CompiledAction(kind="goto", step_n=1, value="https://shop.test/a"),
        CompiledAction(kind="goto", step_n=1),
        CompiledAction(kind="click", step_n=2, locator=loc("role")),
        CompiledAction(kind="click", step_n=2, locator=loc("placeholder")),
        CompiledAction(kind="click", step_n=2, locator=loc("test_id")),
        CompiledAction(kind="click", step_n=2, locator=loc("css")),
        CompiledAction(kind="select", step_n=3, locator=loc("label"), value="x"),
        CompiledAction(kind="check", step_n=3, locator=loc("label")),
        CompiledAction(kind="press", step_n=3),
        CompiledAction(kind="expect_url", step_n=4),
        CompiledAction(kind="expect_hidden", step_n=4, locator=loc("text")),
        CompiledAction(kind="expect_visible", step_n=4, locator=loc("text")),
        CompiledAction(kind="fill", step_n=4, locator=loc("label")),
    ]
    src = render(CompiledCase(case_id="c", code="!!!", actions=actions), "http://x", "e", None)
    ast.parse(src)
    needles = ["get_by_role('button'", "get_by_placeholder", "get_by_test_id",
               "page.locator('v')", "select_option", ".check()", "keyboard.press('Enter')",
               "to_have_url", "to_be_hidden", "def test_case(", "(none: the Judge"]  # fmt: skip
    for needle in needles:
        assert needle in src


def test_action_without_locator_is_rejected() -> None:
    bad = CompiledCase(case_id="c", code="X", actions=[CompiledAction(kind="click", step_n=1)])
    with pytest.raises(ValueError, match="locator"):
        render(bad, "http://x", "e", None)


@pytest.mark.parametrize("src", ["import subprocess\n", "from socket import socket\n",
                                 "from . import x\n"])  # fmt: skip
def test_import_allow_list(src: str) -> None:
    with pytest.raises(ImportNotAllowedError):
        check_imports(src)
    check_imports("import os\nfrom playwright.sync_api import Page\n")
