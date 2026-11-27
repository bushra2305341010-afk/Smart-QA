import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PLAN, RUN, plan } from "../../test/fixtures";
import { ENV, runSummary } from "../../test/runFixtures";
import { PID, errorBody, expectNoAxeViolations, mockApi, renderApp, shellRoutes, type Routes } from "../../test/utils";

const page = `/projects/${PID}/runs`;
const done = { body: { current: { stage: "done", status: "done", entered_at: "2026-11-26T10:00:00Z" }, history: [] } };
const env = { id: ENV, name: "Staging", kind: "staging", base_url: "https://staging.example.com", allowed_hosts: ["staging.example.com"] };

function routes(over: Routes = {}): Routes {
  return {
    ...shellRoutes(),
    [`GET /projects/${PID}/runs`]: { body: { items: [runSummary], next_cursor: null } },
    [`GET /projects/${PID}/environments`]: { body: [env] },
    [`GET /projects/${PID}/plans`]: {
      body: [{ ...plan, id: PLAN, status: "approved", segments: [...plan.segments, { ...plan.segments[0]!, id: "seg_2", journey: "Sign in" }] }],
    },
    ...over,
  };
}

describe("RunsPage", () => {
  it("lists runs with status, environment and coloured verdict counts", async () => {
    mockApi(routes());
    const { container } = renderApp(page);
    const link = await screen.findByRole("link", { name: new RegExp(`open run ${RUN}`) });
    expect(link).toHaveAttribute("href", `/projects/${PID}/runs/${RUN}`);
    const row = link.closest("tr")!;
    expect(within(row).getByText("✓ Completed")).toBeInTheDocument();
    expect(within(row).getByText("Staging")).toBeInTheDocument();
    expect(within(row).getByText("1 Pass")).toBeInTheDocument();
    expect(within(row).getByText("1 Unable to Verify")).toBeInTheDocument();
    expect(within(row).queryByText(/Flaky/)).not.toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("disables the start form with an explanation until the pipeline is done", async () => {
    mockApi(routes());
    const { container } = renderApp(page);
    const button = await screen.findByRole("button", { name: "Start run" });
    expect(button).toBeDisabled();
    expect(await screen.findByText(/It is now at "graph_review" \(awaiting approval\)/)).toBeInTheDocument();
    expect(button).toHaveAccessibleDescription(/Regression runs start when the pipeline is done/);
    await expectNoAxeViolations(container);
  });

  it("explains when the pipeline has not started", async () => {
    mockApi(routes({ [`GET /projects/${PID}/pipeline`]: { body: { current: null, history: [] } } }));
    renderApp(page);
    expect(await screen.findByText(/The pipeline has not started yet/)).toBeInTheDocument();
  });

  it("starts a regression run with an environment and journeys", async () => {
    const calls = mockApi(
      routes({
        [`GET /projects/${PID}/pipeline`]: done,
        [`POST /projects/${PID}/runs`]: { status: 202, body: { stage: "compile", status: "queued" } },
      }),
    );
    const { container } = renderApp(page);
    await screen.findByRole("option", { name: "Staging (staging)" });
    await userEvent.selectOptions(screen.getByLabelText("Environment"), ENV);
    await userEvent.click(await screen.findByRole("checkbox", { name: "Sign in" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Checkout" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Checkout" }));
    const button = screen.getByRole("button", { name: "Start run" });
    await vi.waitFor(() => expect(button).toBeEnabled());
    await userEvent.click(button);
    expect(await screen.findByText(/Run requested \(compile, queued\)/)).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ env_id: ENV, journeys: ["Sign in"], source: "ui" });
    await expectNoAxeViolations(container);
  });

  it("sends the project default environment and shows a 409", async () => {
    const calls = mockApi(
      routes({
        [`GET /projects/${PID}/pipeline`]: done,
        [`GET /projects/${PID}/plans`]: { body: [] },
        [`POST /projects/${PID}/runs`]: {
          status: 409,
          body: errorBody("STATE_CONFLICT", "Event run_requested not allowed in stage execute"),
        },
      }),
    );
    renderApp(page);
    const button = await screen.findByRole("button", { name: "Start run" });
    await vi.waitFor(() => expect(button).toBeEnabled());
    expect(screen.queryByRole("group", { name: /Journeys/ })).not.toBeInTheDocument();
    await userEvent.click(button);
    expect(await screen.findByText("Run not started")).toBeInTheDocument();
    expect(screen.getByText("Event run_requested not allowed in stage execute")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ env_id: null, journeys: [], source: "ui" });
  });

  it("shows the empty state and a note when more runs exist", async () => {
    mockApi(routes({ [`GET /projects/${PID}/runs`]: { body: { items: [], next_cursor: null } } }));
    const { container } = renderApp(page);
    expect(await screen.findByText("No runs yet")).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("shows unfinished runs and a cut-off note", async () => {
    mockApi(
      routes({
        [`GET /projects/${PID}/runs`]: {
          body: { items: [{ ...runSummary, status: "queued", started_at: null, finished_at: null, totals: { cases: 3 } }], next_cursor: "x" },
        },
      }),
    );
    renderApp(page);
    expect(await screen.findByText("No verdicts yet")).toBeInTheDocument();
    expect(screen.getByText("○ Queued")).toBeInTheDocument();
    expect(screen.getAllByText("—")).toHaveLength(2);
    expect(screen.getByText("Showing the latest 50 runs.")).toBeInTheDocument();
  });

  it("shows load errors", async () => {
    mockApi(
      routes({
        [`GET /projects/${PID}/runs`]: { status: 500, body: errorBody("INTERNAL", "Down") },
        [`GET /projects/${PID}/environments`]: { status: 403, body: errorBody("FORBIDDEN", "No") },
      }),
    );
    renderApp(page);
    expect(await screen.findByText("Could not load runs")).toBeInTheDocument();
    expect(await screen.findByText("Could not load environments")).toBeInTheDocument();
  });
});
