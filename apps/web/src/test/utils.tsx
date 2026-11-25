/** Test helpers: a fake API behind `fetch`, providers + router, and an axe check. */
import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import axe from "axe-core";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { makeQueryClient } from "../app/queryClient";
import { AppRoutes } from "../app/routes";
import { ROUTER_FUTURE } from "../app/routerFuture";

export type Call = { method: string; path: string; search: URLSearchParams; body: unknown; headers: Headers };
type Reply = { status?: number; body?: unknown } | ((call: Call) => { status?: number; body?: unknown });
export type Routes = Record<string, Reply>;

export const PID = "prj_" + "a".repeat(32);

export function errorBody(code: string, message: string, details: Record<string, unknown> = {}) {
  return { error: { code, message, details, trace_id: "trace123" } };
}

/** Defaults every signed-in screen needs (session, project list, stepper, cost meter). */
export function shellRoutes(): Routes {
  return {
    "GET /me": { body: { id: "usr_1", email: "lead@example.com", memberships: [] } },
    "GET /projects": {
      body: [{ id: PID, name: "Shop", role: "qa_lead", retention_days: 30, stage: "graph_review", created_at: "2026-11-20T10:00:00Z" }],
    },
    [`GET /projects/${PID}`]: {
      body: { id: PID, name: "Shop", role: "qa_lead", retention_days: 30, stage: "graph_review", created_at: "2026-11-20T10:00:00Z" },
    },
    [`GET /projects/${PID}/pipeline`]: {
      body: { current: { stage: "graph_review", status: "awaiting_approval", entered_at: "2026-11-20T10:00:00Z" }, history: [] },
    },
    [`GET /projects/${PID}/costs`]: {
      body: { month: { spent_usd: "2.50", cap_usd: "10.00", remaining_usd: "7.50" }, by_stage: [], by_run: [], by_month: [] },
    },
  };
}

/**
 * Replace `fetch` with a router over `routes` ("METHOD /path" without /api/v1 or query).
 * Unknown routes answer 404 in the API envelope. Returns the recorded calls.
 */
export function mockApi(routes: Routes): Call[] {
  const calls: Call[] = [];
  const fake = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = new URL(String(input), "http://localhost");
    const method = (init?.method ?? "GET").toUpperCase();
    const path = url.pathname.replace(/^\/api\/v1/, "");
    let body: unknown = init?.body;
    if (typeof body === "string") body = JSON.parse(body);
    const call: Call = { method, path, search: url.searchParams, body, headers: new Headers(init?.headers) };
    calls.push(call);
    const reply = routes[`${method} ${path}`];
    const r = typeof reply === "function" ? reply(call) : reply;
    if (!r) return json(404, errorBody("NOT_FOUND", `No mock for ${method} ${path}`));
    if ((r.status ?? 200) === 204) return new Response(null, { status: 204 });
    return json(r.status ?? 200, r.body ?? {});
  };
  vi.stubGlobal("fetch", vi.fn(fake));
  return calls;
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** Render the whole app (shell + routes) at `route`. */
export function renderApp(route: string) {
  return renderWith(<AppRoutes />, route);
}

export function renderWith(ui: ReactElement, route = "/") {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { ...client.getDefaultOptions().queries, retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]} future={ROUTER_FUTURE}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Assert axe finds no WCAG 2.1 A/AA violations (colour contrast needs a real browser). */
export async function expectNoAxeViolations(container: Element): Promise<void> {
  const result = await axe.run(container, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"] },
    rules: { "color-contrast": { enabled: false }, region: { enabled: false } },
  });
  const summary = result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
  if (summary.length) throw new Error(`axe violations:\n${summary.join("\n")}`);
}
