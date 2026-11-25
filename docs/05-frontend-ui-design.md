# 05 · Frontend UI Design

## 1. What the UI must do well

The users are QA Leads and testers reviewing a lot of AI output. The UI wins if it makes **review fast and trust visible**:
- See the source quote next to every AI claim.
- Approve / reject with one key.
- Read verdicts at a glance (colour + icon + word, never colour alone).
- Dense tables that still breathe.

## 2. Tool analysis

### 2.1 Design tools

| Tool | Strength | Weakness | Use it for |
|---|---|---|---|
| **Figma** | Industry standard, components, variables (tokens), Dev Mode, free for students | Design ≠ code; must be kept in sync | **Main design file**: tokens, components, 8 screens |
| Claude (Artifacts / design) | Turns a written spec into a working HTML/React prototype fast | Less pixel control | Quick clickable prototypes to test flows |
| Canva | Fast, beautiful marketing visuals | Not for app UI | Poster, slides, social posts |
| Penpot | Open source Figma alternative | Smaller plugin ecosystem | If Figma is unavailable |
| Storybook | Components in isolation, a11y addon | Setup time | Living component library in code |

### 2.2 Front-end stacks compared

| Option | Score /5 | Notes |
|---|---|---|
| **React + Vite + TypeScript + Tailwind + shadcn/ui (Radix)** | **4.7** | Fast dev server, accessible primitives, you own the component code, huge ecosystem, React Flow for the graph |
| Next.js + Tailwind | 4.2 | SSR/SEO not needed behind login; more moving parts |
| Vue 3 + Vite + PrimeVue | 3.9 | Good, but React Flow / TanStack ecosystem fits better |
| Angular + Material | 3.4 | Heavy for a 2-person team |
| Svelte + Skeleton | 3.6 | Smaller hiring/plugin pool |

### 2.3 Chosen stack

| Need | Library |
|---|---|
| Framework | React 18, TypeScript (strict), Vite |
| Styling | Tailwind CSS with CSS-variable tokens |
| Components | shadcn/ui (Radix primitives: Dialog, Tabs, Popover, Tooltip, DropdownMenu, Toast) |
| Icons | lucide-react |
| Data fetching | TanStack Query (cache, retries, optimistic updates) |
| Tables | TanStack Table + virtualisation (`@tanstack/react-virtual`) |
| Graph canvas | React Flow (`@xyflow/react`) with dagre/elk auto-layout |
| Charts | Recharts (trend, coverage heatmap) |
| Forms | React Hook Form + Zod (schemas generated from OpenAPI) |
| Routing | React Router v6 |
| Live updates | Server-Sent Events (`EventSource`) |
| Evidence viewer | Playwright trace viewer (embedded iframe), HAR table, `<video>` |
| i18n | i18next (English, Bangla in v1) — use **Hind Siliguri** / **Noto Sans Bengali** for Bangla |
| API client | `openapi-typescript` types generated from FastAPI's OpenAPI + a small typed fetch wrapper (`src/api/client.ts`) |
| Tests | Vitest + Testing Library, Playwright E2E, axe in Storybook |

### 2.4 Integration (how the frontend plugs into the backend)

1. FastAPI publishes `/api/v1/openapi.json`. `pnpm gen:api` generates `apps/web/src/api/schema.d.ts` (types only; Zod schemas later with forms).
2. All requests go through `api()` in `src/api/client.ts`: cookie auth, `X-CSRF-Token` echoed from the `saq_csrf` cookie on state-changing calls, one `/auth/refresh` retry on 401, and `ApiError` built from the error envelope.
3. TanStack Query keys follow `[domain, projectId, id]`. Mutations invalidate the matching keys.
4. SSE `/api/v1/projects/{id}/events` pushes stage and run updates; a hook `useProjectEvents()` patches the Query cache. (Until it exists, the pipeline query polls every 10 s.)
5. Feature flags from `/api/v1/me` decide which screens are visible (MVP vs v1).

## 3. Colour system

Concept: **"Verified Indigo"** — deep navy for focus and authority, indigo as the brand action colour, teal for *verified / cited* (our core promise), and a strict semantic set for verdicts. All text pairs meet WCAG AA (≥ 4.5:1).

### 3.1 Brand and neutrals

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#F8FAFC` | `#0B1120` | App background |
| `--surface` | `#FFFFFF` | `#111827` | Cards, tables |
| `--surface-2` | `#F1F5F9` | `#1E293B` | Hover, zebra rows |
| `--border` | `#E2E8F0` | `#334155` | Dividers |
| `--text` | `#0F172A` | `#E2E8F0` | Body text |
| `--text-muted` | `#475569` | `#94A3B8` | Secondary text |
| `--sidebar` | `#0F172A` | `#020617` | Navigation rail |
| `--primary` | `#4338CA` | `#818CF8` | Buttons, links, focus |
| `--primary-hover` | `#3730A3` | `#A5B4FC` | Hover |
| `--accent` | `#0D9488` | `#2DD4BF` | Verified citation, success highlights |
| `--focus-ring` | `#6366F1` | `#A5B4FC` | 2px outline + 2px offset |
| `--quote-bg` | `#FEF9C3` | `#422006` | Highlighted source quote |

### 3.2 Verdict colours (always with icon + label)

| Verdict | Text | Background | Icon (lucide) |
|---|---|---|---|
| Pass | `#15803D` | `#DCFCE7` | `CheckCircle2` |
| Fail | `#B91C1C` | `#FEE2E2` | `XCircle` |
| Flaky | `#B45309` | `#FEF3C7` | `Shuffle` |
| Blocked | `#475569` | `#E2E8F0` | `Ban` |
| Test Error | `#7E22CE` | `#F3E8FF` | `Wrench` |
| Unable to Verify | `#1D4ED8` | `#DBEAFE` | `HelpCircle` |

Severity: Critical `#7F1D1D`, High `#B91C1C`, Medium `#B45309`, Low `#475569`.

### 3.3 Typography & spacing

- UI font **Inter** (400/500/600/700); code & IDs **JetBrains Mono**; Bangla **Hind Siliguri**.
- Scale: 12 / 14 (body) / 16 / 20 / 24 / 30. Line height 1.5 body, 1.25 headings.
- 4-px spacing grid; radius 8 px (cards 12 px); shadow only on overlays.
- Density toggle: comfortable (row 44 px) / compact (row 32 px).

```css
:root{
  --bg:#F8FAFC;--surface:#FFFFFF;--surface-2:#F1F5F9;--border:#E2E8F0;
  --text:#0F172A;--text-muted:#475569;--sidebar:#0F172A;
  --primary:#4338CA;--primary-hover:#3730A3;--accent:#0D9488;--focus-ring:#6366F1;
  --pass:#15803D;--pass-bg:#DCFCE7;--fail:#B91C1C;--fail-bg:#FEE2E2;
  --flaky:#B45309;--flaky-bg:#FEF3C7;--blocked:#475569;--blocked-bg:#E2E8F0;
  --testerr:#7E22CE;--testerr-bg:#F3E8FF;--uv:#1D4ED8;--uv-bg:#DBEAFE;
}
```

## 4. Layout

```
┌──────┬───────────────────────────────────────────────────────────┐
│ Nav  │ Top bar: project switcher · stage stepper · cost meter · user│
│ rail ├───────────────────────────────────────────────────────────┤
│      │ Page header: title · primary action (Approve) · filters   │
│ 64px │ ┌───────────────────────────┬──────────────────────────┐ │
│      │ │ Main list / canvas        │ Detail panel (source     │ │
│      │ │ (table, graph)            │ quote, evidence, history)│ │
│      │ └───────────────────────────┴──────────────────────────┘ │
└──────┴───────────────────────────────────────────────────────────┘
```

The **stage stepper** (Ingest → Understand → Plan → Design → Run → Report) is always visible; a lock icon shows unapproved gates.

## 5. Screens

| Screen | Key components | UX rules |
|---|---|---|
| Setup wizard | Stepper, file drop, env form, **data-sharing summary** | Show exactly what leaves the machine before "Start" |
| Brief & graph review | React Flow canvas, node side panel with quote, conflict list, question list | Unapproved nodes dashed; approve with `A`, reject `R`, next `J/K` |
| Coverage plan | Editable table (segment, techniques, suggested, approved count, risk badge), cost bar | Edited cells marked; total cost updates live |
| Case review | Split view: case ↔ cited quote ↔ screen screenshot | One key approve; UV cases filtered first |
| Run dashboard | Status tiles per verdict, live list, evidence drawer (trace, video, HAR, console) | SSE updates, no page refresh |
| Bug review | Draft editor, duplicate warning, tracker picker | Nothing filed without explicit "Confirm & file" |
| Reports | Excel / evidence-pack buttons, coverage heatmap, trend chart | Downloads named `project_run_date.xlsx` |
| Settings | Users & roles, model policy, budgets, retention, integrations | Destructive actions need typed confirmation |
| Sign-in | Email + password, then a 6-digit code when two-factor is on; Security page turns two-factor on | Secret shown once |

**Built so far (M07, `apps/web`):** sign-in/register with the two-factor step, security (two-factor setup), projects, setup (upload, Git import, environments, start/retry/cancel), graph review as a node list + detail panel with source quotes (React Flow canvas later), coverage plan, case review, bug review, reports (downloads per run; run ids come from bugs until a runs list exists), and a routed Runs placeholder. Dark mode follows `prefers-color-scheme`, or the theme picker in the top bar sets `html[data-theme]`.

## 6. UX rules

1. Every AI-generated item shows a small **"AI · cited"** or **"AI · unverified"** chip.
2. Never show a green pass without its evidence one click away.
3. Empty states teach the next step ("No graph yet — upload a PRD or connect a repo").
4. Loading: skeletons for < 2 s, progress with stage name for long jobs.
5. Errors: say what happened, why, and the next action; include `trace_id` to copy.
6. Keyboard everywhere; visible focus ring; `?` opens the shortcut sheet.
7. Respect `prefers-reduced-motion` and `prefers-color-scheme`.
8. Responsive down to 1024 px for review; read-only dashboards down to 375 px.

## 7. Front-end folder structure

```
apps/web/src/
  api/            generated types (schema.d.ts), fetch wrapper, query hooks
  app/            router, providers, layout (nav rail, top bar)
  components/ui/  shadcn components (owned)
  components/     VerdictBadge, CitationQuote, EvidenceDrawer, StageStepper, CostMeter, StatusBadge, States
  features/       auth/, projects/, setup/, graph/, plan/, cases/, runs/, bugs/, reports/, settings/
  hooks/          useProjectEvents, useHotkeys, useProjectId
  test/           mockApi, renderApp, axe helper, fixtures
  i18n/           en.json, bn.json
  styles/         tokens.css, globals.css (Tailwind maps every colour to a token)
```

## 8. Done checklist for any screen

- [ ] Uses tokens only (no raw hex in components)
- [ ] Keyboard + screen-reader tested; axe = 0 violations
- [ ] Light and dark checked
- [ ] Empty, loading, error states
- [ ] Strings in i18n file
- [ ] Playwright E2E for the main path
