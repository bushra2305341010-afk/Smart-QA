# Stuti's Guide: Fork, Set Up, Build, Test, Document, Contribute

Hi Stuti! This is your personal guide to contributing to Smart Autonomous QA. Follow it top to bottom the first time; after that, §3 (daily workflow) is all you need.

**Your areas (from [docs/16-project-implementation.md](docs/16-project-implementation.md) §1):**
**Runner** (runs tests in the browser) · **Judge** (decides each verdict) · **Web App** (the UI) · plus the **Safe-action policy** and **Golden project 2 (school)**.

| In simple words | What you build |
|---|---|
| Runner | Opens a real browser in a safe container, runs each test step, and saves proof (screenshots, trace, network log) |
| Judge | When a test fails, re-runs it to check whether it's a real bug or a glitch, then gives an honest verdict with a reason |
| Web App | The screens people use: review the plan, watch tests run live, confirm bugs, download reports |
| Policy | Code that blocks dangerous actions (delete, pay, send email, leave the allowed website) |

---

## 1. One-time setup (about 30 minutes)

### 1.1 Install tools (macOS; Windows → use WSL2 Ubuntu and `apt`/`curl` equivalents)

```bash
# Homebrew first if you don't have it: https://brew.sh
brew install git gh uv node pnpm
brew install --cask docker          # then open Docker Desktop once
uv python install 3.12
```

Check:
```bash
git --version && gh --version && uv --version && node -v && pnpm -v && docker --version
```

### 1.2 Log in to GitHub from the terminal

```bash
gh auth login          # GitHub.com → HTTPS → login with browser
git config --global user.name  "Somprity Roy Stuti"
git config --global user.email "<the email on your GitHub account>"
```

### 1.3 Fork and clone

```bash
# Creates YOUR copy at github.com/<your-username>/Smart-QA and clones it
gh repo fork bushra2305341010-afk/Smart-QA --clone
cd Smart-QA
git remote -v
# origin    → your fork          (you push here)
# upstream  → bushra2305341010-afk/Smart-QA  (the main repo; you pull from here)
```
If `upstream` is missing: `git remote add upstream https://github.com/bushra2305341010-afk/Smart-QA.git`

### 1.4 Install the project

```bash
cp .env.example .env              # local settings (never commit .env)
make install                      # Python deps + git hooks (ruff, gitleaks)
cd apps/web && pnpm install && cd ../..
```

### 1.5 Verify everything works

```bash
make test                         # lint + type check + Python unit tests → all green
cd apps/web && pnpm test && pnpm typecheck && cd ../..
docker compose up -d              # Postgres, Redis, S3 (SeaweedFS), API
curl http://localhost:8000/api/v1/readyz     # → {"status":"ready",...}
cd apps/web && pnpm dev           # open http://localhost:5173 → you see the verdict badges
```

If any step fails, see §8 (troubleshooting).

---

## 2. How contribution works (the big picture)

```
upstream/main ──(sync)──▶ your local main ──(branch)──▶ feat/T-301-policy
      ▲                                                     │ code + tests + docs
      │                                                     ▼
      └──── PR (review + green CI, then squash merge) ◀── push to your fork (origin)
```

- **Never** commit directly to `main`.
- **One task = one branch = one PR.** Small PRs (under ~400 changed lines) get reviewed faster.
- Nadia reviews your PRs; you review hers. Merge only when CI is green.

---

## 3. Daily workflow (copy-paste)

```bash
# 1) Sync with the main repo
git checkout main
git fetch upstream
git merge --ff-only upstream/main
git push origin main

# 2) Pick your next task in docs/26-task-board.md, set it to `doing`, then branch
git checkout -b feat/T-301-safe-action-policy

# 3) Write the failing tests first, then the code (see §5 for what to test)
make test-fast                       # Python
cd apps/web && pnpm test && cd ../.. # Web

# 4) Update docs (see §6), then commit
git add -A
git commit -m "feat(policy): block destructive and off-domain actions (T-301)"

# 5) Push to YOUR fork and open the PR into the main repo
git push -u origin feat/T-301-safe-action-policy
gh pr create --repo bushra2305341010-afk/Smart-QA --base main \
  --title "feat(policy): safe-action policy (T-301)" --body-file .github/pull_request_template.md
# then edit the PR description on GitHub: fill in what/why, tests run, docs updated

# 6) After review comments: fix, commit, push again (the PR updates automatically)

# 7) After merge: clean up
git checkout main && git fetch upstream && git merge --ff-only upstream/main
git branch -d feat/T-301-safe-action-policy
```

**Commit message format:** `type(scope): what changed (task ID)`. Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`.

---

## 4. Your modules, in order

Each module is a PR (bigger modules may be 2–3 PRs). Dependencies tell you what must be merged first.

| Module | Task IDs | What you build | Main files | Depends on | Done when |
|---|---|---|---|---|---|
| **M03 Safe-action policy** | T-301…T-303 | Rules that classify an action (click/type/navigate/request) as allowed or blocked, with a reason; domain allow-list; role permission matrix | `packages/policy/actions.py`, `domains.py`, `permissions.py` | M01 | 100% branch coverage; every row of [docs/09-security.md](docs/09-security.md) §6 has a test |
| **M05 Verdict rules** | T-501…T-504 | Pure functions: `decide_verdict(result, rerun, citation, detectors) → Verdict(verdict, confidence, reason, rule)`; flake features; confidence | `packages/verdicts/rules.py`, `flake.py`, `confidence.py` | M02 contracts | Table-driven tests cover all 6 verdicts and every rule J1–J7 in [docs/08-agent.md](docs/08-agent.md) §5 |
| **M07 Web foundations** | T-701…T-706 | Tailwind + tokens, app layout (nav rail, top bar, stage stepper), router, API client generation, `CitationQuote`, `EvidenceDrawer` shells, dark mode | `apps/web/src/app/`, `components/` | M01 | axe = 0 violations, keyboard works, light + dark screenshots in PR |
| **M10 Runner** | T-1001…T-1008 | Runner process: register (mTLS later), pull job, run a compiled Playwright test in a fresh browser context, capture evidence per step, SHA-256 hash, upload, report result; policy hook; Blocked detectors (CAPTCHA/MFA) | `apps/runner/` | M03, M08 | Runs the sample test against golden project 2 with full evidence; kill-and-resume test passes |
| **M10b Judge worker** | T-1011…T-1013 | Worker that uses M05 rules, requests a clean re-run, writes verdict + reason | `apps/workers/judge/` | M05, M10 | Flake classification ≥ 85% on the labelled set |
| **M12 Run dashboard + bug review UI** | T-1201…T-1206 | Live run screen (SSE), verdict tiles, evidence viewer, bug review screen with "Confirm & file" | `apps/web/src/features/runs/`, `features/bugs/` | M07, M10b | Playwright e2e: start run → see live verdicts → confirm a bug |
| **Golden project 2 (school)** | T-005 | Small school-management app + PRD + manual + OpenAPI + 15–20 seeded bugs (list in `evals/private/`, never committed) | `evals/golden_projects/school/` | — | Used by evals from week 6 |

Exact acceptance criteria are in [docs/25-user-stories-and-acceptance.md](docs/25-user-stories-and-acceptance.md) (US-06, US-07, US-08, US-11) and in each sector file under [docs/workflows/](docs/workflows/).

---

## 5. Testing plan (for your modules)

### 5.1 The rule

**Tests first, then code. A PR without tests is not reviewed.** Never mark a task done with a failing or skipped test.

### 5.2 What to test, per module

| Module | Test type | What exactly | File | Target |
|---|---|---|---|---|
| M03 Policy | Unit, table-driven | Each blocked category (delete, pay, transfer, email, off-domain, file upload) × allowed/blocked; production env; env marked safe; case-insensitive matching; aria-label vs button text | `tests/policy/test_actions.py` | **100% branches** (`make cov`) |
| M03 Permissions | Unit | Every cell of the RBAC matrix in [docs/10](docs/10-authentication-and-security.md) §4; Tester cannot self-approve | `tests/policy/test_permissions.py` | 100% branches |
| M05 Verdicts | Unit, table-driven | One test per rule: pass+verified → Pass; pass+no citation → UV; blocked detector → Blocked; locator fault → Test Error; fail then pass with noise → Flaky; fail twice same + verified → Fail; weak evidence → UV; confidence levels | `tests/verdicts/test_rules.py` | 100% branches; **a Pass without a verified citation must be impossible** |
| M07 Web | Component (Vitest + Testing Library) | Renders, keyboard navigation, accessible names, empty/loading/error states | `*.test.tsx` next to the component | Every component has a test |
| M07 Web | Accessibility | axe checks on each screen | `src/test/a11y.test.tsx` | 0 violations |
| M10 Runner | Unit | Evidence hashing, step capture in `finally`, policy hook blocks before the action runs, detector signatures | `tests/runner/` | 90% lines |
| M10 Runner | Integration (`@pytest.mark.integration`) | Run a real Playwright test against a tiny local page; evidence files exist and hashes match; container/browser cleaned up | `tests/runner/test_run_integration.py` | Green in CI |
| M10 Runner | Chaos | Kill the runner mid-run → run resumes from `last_completed_case_id`, no duplicate results | `tests/chaos/` | Green before M10 merges |
| M10b Judge | Eval | Labelled flake set in `evals/datasets/flakes.jsonl` | `evals/run_evals.py --set small` | ≥ 85% |
| M12 UI | End to end (Playwright) | Start a run → live verdicts appear → open evidence → confirm a bug | `apps/web/e2e/` | Green on merge to main |
| Security | Red-team pages | Hostile pages (hidden text, fake dialogs, "delete all users" in alt text): runner must not perform any off-plan action | `tests/redteam/` | 0 off-plan actions |

### 5.3 Commands

```bash
make test-fast                 # Python unit tests
make cov                       # coverage report with missing lines
make test-int                  # integration tests (docker compose up -d db redis first)
uv run pytest tests/policy -q  # one folder
cd apps/web && pnpm test       # web unit/component tests
```

### 5.4 Test writing tips

- **Table-driven** (`@pytest.mark.parametrize`) for rules: one row per case, readable like a spec.
- Test **behaviour**, not implementation: "Delete button is blocked" rather than "function X called Y".
- No real personal data in fixtures. Use made-up names and `example.com` emails.
- When you fix a bug, first write a test that fails because of it.

---

## 6. Documentation plan (what you update, and when)

| When you… | Update |
|---|---|
| Finish any task | Task status in [docs/26-task-board.md](docs/26-task-board.md) and one line in [docs/CHANGELOG.md](docs/CHANGELOG.md) under *Unreleased* |
| Change the Runner / Judge / Policy / UI flow or files | Your sector file: [05-executor-and-runner](docs/workflows/05-executor-and-runner.md), [06-judge](docs/workflows/06-judge.md), [10-governance-and-auth](docs/workflows/10-governance-and-auth.md), [11-frontend](docs/workflows/11-frontend.md). Keep the **Code map**, **Bug locator** and **Change safety** sections true |
| Fix a new kind of bug | Add a row to that sector's **Bug locator** (symptom → file → fix) |
| Add or change an API endpoint | [docs/06-api.md](docs/06-api.md) |
| Add a DB table/column | [docs/07-database.md](docs/07-database.md) |
| Change the runner protocol | [docs/06-api.md](docs/06-api.md) §5 + bump the protocol version |
| Make a design decision | New ADR in [docs/adr/](docs/adr/) using `000-template.md` |
| Change a screen or colour | [docs/05-frontend-ui-design.md](docs/05-frontend-ui-design.md) |
| End of your week (Friday) | Your part of the weekly entry in [docs/20-continuous-update.md](docs/20-continuous-update.md) §3 |
| Something important changes for future sessions | The **Status** section of [CLAUDE.md](CLAUDE.md) |

Docs go in the **same PR** as the code they describe.

---

## 7. Before you open a PR (checklist)

- [ ] Branch is up to date with `upstream/main`
- [ ] `make test` green · `pnpm test && pnpm typecheck` green (if web)
- [ ] New code has tests; coverage target met for your module
- [ ] Sector's **Change safety** list run (from its file in `docs/workflows/`)
- [ ] Docs updated (§6) · CHANGELOG line · task board status
- [ ] No secrets, `.env`, or real personal data in the diff (`git diff --staged`)
- [ ] PR description filled in: what/why, tests run, docs updated, screenshots for UI

---

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| `uv: command not found` | `brew install uv`, then open a new terminal |
| `make install` fails on Python version | `uv python install 3.12` |
| Docker commands hang | Open Docker Desktop and wait until it says "running" |
| Port 5432/6379/8000 already in use | Stop the other service, or change the port in `docker-compose.yml` locally (don't commit it) |
| `git push` rejected | You're pushing to `upstream` by mistake; push to `origin` (your fork) |
| PR shows unrelated changes | Sync main (§3 step 1), then `git rebase main` on your branch and `git push --force-with-lease` |
| pre-commit blocks the commit | Read the message; usually `make fmt` fixes formatting. Gitleaks means a secret: remove it |
| CI fails but local passes | Open the failing job log on GitHub; run the same command locally from a clean `uv sync` |

---

## 9. Using Claude Code (optional, recommended)

The repo's [CLAUDE.md](CLAUDE.md) tells Claude Code the project rules and working loop. In the repo folder:

```bash
claude
> Read CLAUDE.md and docs/26-task-board.md. Start task T-301 (safe-action policy) on a new branch: tests first, then code, then update the docs.
```

Always review what it writes, run the tests yourself, and keep PRs small.

---

Questions? Leave a comment on the PR or the task's issue, and mention Nadia.
