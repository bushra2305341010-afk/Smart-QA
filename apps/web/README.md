# Web App

React 18 + TypeScript (strict) + Vite + Tailwind SPA for the four human gates: setup, graph review (Gate 1), coverage plan (Gate 2), case review (Gate 3), bug review (Gate 4), reports. The run dashboard is a routed placeholder.

| | |
|---|---|
| Design doc | docs/05-frontend-ui-design.md, docs/workflows/11-frontend.md (code map, screen → API) |
| Owner | Stuti |
| Module | M07 web foundations + T-105 web shell |

## Commands

```bash
pnpm install
pnpm dev          # http://localhost:5173, /api proxied to the API on :8000
pnpm test         # Vitest + Testing Library + axe (fetch is mocked; no backend needed)
pnpm typecheck
pnpm lint         # typescript-eslint, react-hooks, jsx-a11y; bans dangerouslySetInnerHTML and raw hex
pnpm build
pnpm gen:api      # regenerate src/api/schema.d.ts from the running API's OpenAPI
```

Run the API with `uv run uvicorn apps.api.main:app --port 8000` (see the repo README). Sign-in uses the API's cookie session; state-changing calls send `X-CSRF-Token` from the `saq_csrf` cookie.

## Rules

- Colours only from `src/styles/tokens.css` (Tailwind classes such as `bg-primary`, `text-uv`).
- Model, document and app-under-test text is rendered as plain text, never as HTML.
- Every screen has loading, empty and error states and an axe test with zero violations.
