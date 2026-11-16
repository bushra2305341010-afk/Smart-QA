# 22 · Coding Standards

One style for the whole repo, so any file reads like the same author wrote it.

## 1. General rules

1. **Clarity over cleverness.** Name things for what they mean in the domain (`verify_quote`, not `check2`).
2. **Small units.** Functions ≤ 40 lines, files ≤ 400 lines; split when bigger.
3. **Pure core, thin edges.** Business rules (coverage formula, verdict rules, policy, citations) are pure functions with no I/O. I/O lives in adapters.
4. **Fail loudly.** Raise typed domain errors; never swallow exceptions; never return `None` to mean "error".
5. **No dead code, no commented-out code, no TODO without an issue link** (`# TODO(#123): …`).
6. **Every public function has a docstring** stating what it does, inputs, outputs and the errors it raises.
7. **Security by default:** never log secrets or PII; validate all input at the boundary; parameterised SQL only.

## 2. Python (backend, workers, runner)

| Topic | Rule |
|---|---|
| Version | 3.12, `from __future__ import annotations` not needed |
| Format / lint | `ruff format`, `ruff check` (rules: E, F, I, B, UP, S, N, SIM, RUF) |
| Types | `mypy --strict` on `packages/`, `--check-untyped-defs` on `apps/` |
| Models | Pydantic v2 for all data crossing a boundary; `model_config = ConfigDict(frozen=True)` for contracts |
| Errors | `class DomainError(Exception)` base; one subclass per error code in [06-api.md](06-api.md) |
| Async | FastAPI routes async; CPU-heavy work goes to Celery, never in the request |
| Imports | absolute; no `from x import *`; layer rule from [02-architecture.md](02-architecture.md) §4 |
| Logging | `structlog`, JSON, with `trace_id`, `project_id`; no f-strings with secrets |
| Tests | `pytest`, file per module `test_<module>.py`, table-driven with `@pytest.mark.parametrize` |
| Naming | `snake_case` functions/vars, `PascalCase` classes, `UPPER_CASE` constants |

## 3. TypeScript (web)

| Topic | Rule |
|---|---|
| Strictness | `"strict": true`, `noUncheckedIndexedAccess`, no `any` (use `unknown` + narrowing) |
| Lint / format | ESLint (typescript-eslint, react-hooks, jsx-a11y, security) + Prettier |
| Components | Function components, one per file, `PascalCase.tsx`; props typed with `type Props = {…}` |
| State | Server state in TanStack Query; local UI state in `useState`; no global store unless justified by an ADR |
| Styling | Tailwind + tokens only; no raw hex in components |
| Data | Only the generated API client; never hand-write fetch calls |
| Model text | Render as text; never `dangerouslySetInnerHTML` |
| Tests | Vitest + Testing Library: test behaviour (what the user sees), not implementation |

## 4. SQL and migrations

- Table names singular `snake_case`; every table has `id`, `project_id`, `created_at`, `updated_at`.
- Foreign keys always indexed. Enums as Postgres enums or check constraints.
- Migrations follow expand → migrate → contract ([07-database.md](07-database.md) §6).

## 5. Prompts (AI)

- File per prompt `name@semver.md`; sections: Role, Task, Rules, Output schema, Examples.
- Untrusted data always wrapped in `<untrusted_…>` tags.
- Any change bumps the version and passes `evals-small`.

## 6. Git

- Branches: `feat/`, `fix/`, `docs/`, `refactor/`, `chore/`, `test/` + ID + short name.
- Conventional Commits; one logical change per commit.
- Squash merge; PR title = final commit message.
- Never commit `.env`, keys, real customer data or large binaries.

## 7. Code review checklist

- [ ] Does it do what the issue asks, and nothing more?
- [ ] Names clear? Functions small? No duplication?
- [ ] Tests cover the happy path, edge cases and errors?
- [ ] Contracts/API/DB changes documented?
- [ ] Security: input validated, permissions checked, nothing sensitive logged?
- [ ] Performance: no N+1 queries, no blocking I/O in async code?
- [ ] Docs and CHANGELOG updated?
