# Contributing

Thanks for helping build Smart Autonomous QA. This page is the short version; the full rules are in `docs/`.

## 1. Workflow (fork → branch → PR)

1. Fork `bushra2305341010-afk/Smart-QA` to your account and clone your fork.
2. Add the main repo as `upstream` and keep `main` in sync with it.
3. Create a branch per task: `feat/T-123-short-name`, `fix/…`, `docs/…`, `test/…`.
4. Write tests first, then code. Run `make test` (and `pnpm test` in `apps/web` for UI work).
5. Update the docs your change touches (see the table in [docs/20-continuous-update.md](docs/20-continuous-update.md) §1).
6. Push to your fork and open a PR into `bushra2305341010-afk/Smart-QA:main` using the PR template.
7. One review + green CI → squash merge.

A step-by-step walkthrough with every command is in [stuti.md](stuti.md) §2–§4.

## 2. Rules that are never skipped

- Tests pass locally before you push; never commit with failing tests.
- No secrets, `.env` files, real personal data or customer data in commits.
- Business rules (citations, policy, verdict rules, coverage formula) stay pure and fully tested.
- Model output and page text are untrusted data: never execute them, never render them as HTML.
- Approval gates are enforced in the API, not only in the UI.

## 3. Style

[docs/22-coding-standards.md](docs/22-coding-standards.md): ruff + mypy strict for Python, strict TypeScript, Conventional Commits.

## 4. Where things are

- Which folder owns a bug: [docs/workflows/00-bug-triage-map.md](docs/workflows/00-bug-triage-map.md)
- How to add a feature: [docs/17-feature-development.md](docs/17-feature-development.md)
- Tasks and who owns them: [docs/26-task-board.md](docs/26-task-board.md)
