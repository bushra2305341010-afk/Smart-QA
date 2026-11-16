# Sector 11 · Frontend

**Screens:** setup wizard, brief & graph review, coverage plan, case review, run dashboard, bug review, reports, settings.
**Owner:** Stuti · Support: Nadia · Design: [../05-frontend-ui-design.md](../05-frontend-ui-design.md)

## Flow

```
OpenAPI ─▶ pnpm gen:api ─▶ typed client + Zod
route ─▶ feature page ─▶ TanStack Query hooks ─▶ API
SSE /events ─▶ useProjectEvents ─▶ patch Query cache ─▶ live UI
```

## Code map

| Concern | Path |
|---|---|
| Router & layout | `apps/web/src/app/` |
| Generated API | `apps/web/src/api/` (do not edit by hand) |
| Shared components | `components/` (VerdictBadge, CitationQuote, EvidenceDrawer, StageStepper, CostMeter) |
| Features | `features/<screen>/` |
| Tokens | `styles/tokens.css` |
| i18n | `i18n/en.json`, `bn.json` |

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Type errors after backend change | Run `pnpm gen:api` | Regenerate client |
| UI not live-updating | `useProjectEvents`, proxy buffering | Event name mismatch; `proxy_buffering off` |
| Stale data after approve | Mutation `onSuccess` | Invalidate correct query keys |
| Colour wrong in dark mode | Hard-coded hex | Use tokens |
| Keyboard shortcut conflicts | `useHotkeys` | Scope by focused panel |
| Model text renders HTML | **High** → component | Never `dangerouslySetInnerHTML`; render as text/markdown-safe |

## Change safety

- [ ] `pnpm test && pnpm typecheck && pnpm lint`
- [ ] `make e2e` for touched screens
- [ ] axe 0 violations, light + dark screenshots in PR
- [ ] Shared component change → Storybook visual check of all usages
