"""Assemble a `CompiledCase` from designed steps + the cited expected result (F20)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from packages.compiler.steps import expected_action, parse_step
from packages.contracts.run import EXPECTATIONS, CompiledAction, CompiledCase


class NotCompilableError(ValueError):
    pass


def compile_case(
    case_id: str,
    code: str,
    steps: Sequence[tuple[int, str]],
    expected_text: str,
    routes: Mapping[str, str] | None = None,
    start_url: str | None = None,
) -> CompiledCase:
    """Grammar-only compile. Unparsed steps are listed so a model can fill just those."""
    actions: list[CompiledAction] = []
    unparsed: list[int] = []
    for n, text in sorted(steps):
        parsed = parse_step(text, n, routes)
        if parsed is None:
            unparsed.append(n)
        else:
            actions.extend(parsed)
    last = max((n for n, _ in steps), default=0)
    check = expected_action(expected_text, last + 1)
    if check is not None:
        actions.append(check)
    elif actions and actions[-1].kind in EXPECTATIONS:  # the last step already checks it
        actions[-1] = actions[-1].model_copy(update={"expected": True})
    else:  # nothing deterministic to check: the model may fill this slot, nothing else may
        unparsed.append(last + 1)
    if not actions:
        raise NotCompilableError(f"{code}: no step could be compiled")
    if start_url is not None and actions[0].kind != "goto":
        actions.insert(0, CompiledAction(kind="goto", step_n=1, value=start_url))
    return CompiledCase(case_id=case_id, code=code, actions=actions, unparsed_steps=unparsed)


def merge(case: CompiledCase, filled: Sequence[CompiledAction]) -> CompiledCase:
    """Add model-compiled actions for unparsed steps only. Anything else the model sent is
    dropped: it may not add, change or remove actions of steps the grammar already compiled,
    and it may mark an action `expected` only when the grammar found no expected-result check."""
    todo = set(case.unparsed_steps)
    extra = [a for a in filled if a.step_n in todo]
    if any(a.expected for a in case.actions):
        extra = [a.model_copy(update={"expected": False}) for a in extra]
    done = {a.step_n for a in extra}
    actions = sorted([*case.actions, *extra], key=lambda a: a.step_n)
    return case.model_copy(update={"actions": actions, "unparsed_steps": sorted(todo - done)})
