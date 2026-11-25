# Sector 11 · Frontend

**Screens:** sign-in / register (+ two-factor step), projects, project setup, graph review (Gate 1), coverage plan (Gate 2), case review (Gate 3), runs (placeholder), bug review (Gate 4), reports, security settings.
**Owner:** Stuti · Support: Nadia · Design: [../05-frontend-ui-design.md](../05-frontend-ui-design.md)

## Flow

```
FastAPI OpenAPI ─▶ pnpm gen:api ─▶ src/api/schema.d.ts (types only)
route ─▶ feature page ─▶ TanStack Query hook (src/api/*.ts) ─▶ api() fetch wrapper ─▶ /api/v1
        cookie session · X-CSRF-Token from the saq_csrf cookie · 401 → one /auth/refresh + retry
mutation onSuccess ─▶ invalidate [domain, projectId, …] ─▶ list + stage stepper refetch
(planned) SSE /events ─▶ useProjectEvents ─▶ patch Query cache ─▶ live UI  (pipeline polls every 10 s until then)
```

## Code map

| Concern | Path |
|---|---|
| Entry, providers, router | `apps/web/src/main.tsx`, `src/app/App.tsx`, `src/app/routes.tsx`, `src/app/queryClient.ts` |
| Layout | `src/app/AppShell.tsx` (skip link, nav rail, top bar), `NavRail.tsx`, `TopBar.tsx`, `ProjectSwitcher.tsx`, `ThemeToggle.tsx`, `RequireAuth.tsx`, `NotFoundPage.tsx` |
| Generated API types | `src/api/schema.d.ts` (do not edit by hand; `pnpm gen:api` with the API on :8000) |
| API client | `src/api/client.ts` (`api()`, `ApiError` from the error envelope, CSRF header, refresh-once), `src/api/types.ts` (named aliases + JSON-column shapes) |
| Query hooks | `src/api/auth.ts`, `src/api/projects.ts` (projects, sources, environments, pipeline, costs), `src/api/review.ts` (graph, plans, cases, bugs) |
| Shared components | `src/components/`: `VerdictBadge`, `CitationQuote`, `StageStepper`, `CostMeter`, `StatusBadge`, `PageHeader`, `States` (Loading / Empty / Error with trace id) |
| Hooks | `src/hooks/useProjectId.ts`, `src/hooks/useHotkeys.ts` (A / R / J / K, ignored while typing) |
| Features | `src/features/auth/`, `projects/`, `setup/`, `graph/`, `plan/`, `cases/`, `bugs/`, `reports/`, `settings/`, `runs/` (placeholder only) |
| Tokens and Tailwind | `src/styles/tokens.css`, `src/styles/globals.css`, `tailwind.config.js` (every colour is a token) |
| Tests | `*.test.ts(x)` next to the code; helpers in `src/test/utils.tsx` (`mockApi`, `renderApp`, `expectNoAxeViolations`), data in `src/test/fixtures.ts` |
| Lint | `eslint.config.js` (typescript-eslint, react-hooks, jsx-a11y; bans `dangerouslySetInnerHTML` and raw hex literals) |
| i18n | not started (`i18n/en.json`, `bn.json` planned) |

## Screen → API

| Route | Screen | Endpoints |
|---|---|---|
| `/login`, `/register` | Sign in (+ TOTP step), create account | `POST /auth/login`, `/auth/login/mfa`, `/auth/register` |
| `/settings/security` | Turn on two-factor | `POST /auth/totp/setup`, `/auth/totp/enable` |
| `/projects` | List, create | `GET/POST /projects` |
| `/projects/:pid/setup` | Sources, Git import, environments, start/retry/cancel | `/sources`, `/sources/upload`, `/sources/repo`, `/environments`, `/pipeline`, `/pipeline/events` |
| `/projects/:pid/graph` | Gate 1 | `/graph`, `/graph/{gv}`, `PATCH …/nodes/{nid}`, `POST …/approve`, event `graph_rejected` |
| `/projects/:pid/plan` | Gate 2 | `/plans`, `PATCH …/segments/{seg}`, `POST …/approve`, event `plan_edited` |
| `/projects/:pid/cases` | Gate 3 | `/cases`, `POST /cases/review`, `POST /cases/approve` |
| `/projects/:pid/runs` | Placeholder (run dashboard + SSE to come) | — |
| `/projects/:pid/bugs` | Gate 4 | `/bugs`, `/bugs/{bug}/duplicates`, `PATCH /bugs/{bug}`, `…/confirm`, `…/dismiss`, `POST /bugs/approve` |
| `/projects/:pid/reports` | Downloads | `/runs/{run}/export.xlsx`, `/runs/{run}/evidence-pack` (run ids from bugs or typed in) |
| top bar | Stepper, cost meter, switcher | `/pipeline`, `/costs`, `/projects`, `/me` |

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Type errors after backend change | Run `pnpm gen:api` | Regenerate `schema.d.ts`, then fix `src/api/types.ts` aliases |
| 403 `CSRF_FAILED` | `src/api/client.ts` `send()` | `saq_csrf` cookie missing (signed out?) or header not echoed |
| Signed out after ~15 min | `refreshOnce()` in `client.ts` | Refresh cookie path is `/api/v1/auth`; proxy must keep it |
| UI not live-updating | `usePipeline` poll / future `useProjectEvents`, proxy buffering | Event name mismatch; `proxy_buffering off` |
| Stale data after approve | Mutation `onSuccess` in `src/api/review.ts` | Invalidate correct query keys (`reviewKeys`, `keys.pipeline`) |
| Colour wrong in dark mode | Hard-coded hex / missing token | Use tokens; `pnpm lint` flags hex literals |
| Keyboard shortcut conflicts | `useHotkeys` | Ignored in inputs; scope by focused panel if needed |
| Model text renders HTML | **High** → component | Never `dangerouslySetInnerHTML`; render as text (lint rule enforces) |
| axe test fails | `src/test/utils.tsx` `expectNoAxeViolations` | Missing label / name / landmark; colour contrast is checked in a real browser, not jsdom |

## Change safety

- [ ] `pnpm test && pnpm typecheck && pnpm lint`
- [ ] `make e2e` for touched screens (Playwright E2E not set up yet)
- [ ] axe 0 violations (every screen test calls `expectNoAxeViolations`), light + dark screenshots in PR
- [ ] Shared component change → check every usage (Storybook not set up yet)
