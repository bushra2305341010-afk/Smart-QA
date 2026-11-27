import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PLAN, plan } from "../../test/fixtures";
import { PID, errorBody, expectNoAxeViolations, mockApi, renderApp, shellRoutes, type Routes } from "../../test/utils";

const base = `/projects/${PID}/plans`;
const page = `/projects/${PID}/plan`;

function routes(extra: Routes = {}): Routes {
  return { ...shellRoutes(), [`GET ${base}`]: { body: [plan] }, ...extra };
}

describe("PlanPage (Gate 2)", () => {
  it("shows counts per technique with reasons, totals and cost", async () => {
    mockApi(routes());
    const { container } = renderApp(page);
    expect(await screen.findByRole("rowheader", { name: /Checkout/ })).toBeInTheDocument();
    expect(screen.getByText("2 roles can check out")).toBeInTheDocument();
    expect(screen.getByText("quantity limit 1 to 99")).toBeInTheDocument();
    expect(screen.getByText("Must")).toBeInTheDocument();
    expect(screen.getByText(/Estimated design cost/)).toHaveTextContent("≈ $1.20 · about 3 min · model claude-opus-5-5");
    await expectNoAxeViolations(container);
  });

  it("edits an approved count", async () => {
    const calls = mockApi(routes({ [`PATCH ${base}/${PLAN}/segments/seg_1`]: { body: { ...plan.segments[0], approved_count: 3 } } }));
    renderApp(page);
    const input = await screen.findByLabelText("Approved count for Checkout");
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
    await userEvent.clear(input);
    await userEvent.type(input, "3");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ approved_count: 3 }));
  });

  it("marks edited segments and scales the cost", async () => {
    const edited = { ...plan, approved_total: 3, segments: [{ ...plan.segments[0]!, approved_count: 3 }] };
    mockApi(routes({ [`GET ${base}`]: { body: [edited] } }));
    renderApp(page);
    expect(await screen.findByText("Edited from 6")).toBeInTheDocument();
    expect(screen.getByText(/Estimated design cost/)).toHaveTextContent("≈ $0.60");
  });

  it("approves the plan", async () => {
    mockApi(routes({ [`POST ${base}/${PLAN}/approve`]: { body: { ...plan, status: "approved" } } }));
    renderApp(page);
    await userEvent.click(await screen.findByRole("button", { name: "Approve plan" }));
    expect(await screen.findByText("Plan approved. Test design starts next.")).toBeInTheDocument();
  });

  it("shows a budget refusal", async () => {
    mockApi(
      routes({
        [`POST ${base}/${PLAN}/approve`]: {
          status: 402,
          body: errorBody("BUDGET_EXCEEDED", "Estimated design cost is above the remaining monthly budget"),
        },
      }),
    );
    renderApp(page);
    await userEvent.click(await screen.findByRole("button", { name: "Approve plan" }));
    expect(await screen.findByText(/above the remaining monthly budget/)).toBeInTheDocument();
  });

  it("re-plans through the pipeline", async () => {
    const calls = mockApi(routes({ [`POST /projects/${PID}/pipeline/events`]: { body: { stage: "plan", status: "queued", entered_at: "" } } }));
    renderApp(page);
    await userEvent.click(await screen.findByRole("button", { name: "Re-plan" }));
    await waitFor(() => expect(calls.find((c) => c.path.endsWith("/pipeline/events"))?.body).toEqual({ event: "plan_edited" }));
  });

  it("is read-only once approved and explains a missing estimate", async () => {
    const approved = { ...plan, status: "approved", cost_estimate: { available: false, reason: "MODEL_PRICE_* not set" } };
    mockApi(routes({ [`GET ${base}`]: { body: [approved] } }));
    renderApp(page);
    expect(await screen.findByText("Cost estimate unavailable: MODEL_PRICE_* not set")).toBeInTheDocument();
    expect(screen.queryByLabelText("Approved count for Checkout")).toBeNull();
    expect(screen.queryByRole("button", { name: "Approve plan" })).toBeNull();
  });

  it("teaches the next step without a plan", async () => {
    mockApi(routes({ [`GET ${base}`]: { body: [] } }));
    const { container } = renderApp(page);
    expect(await screen.findByText("No plan yet")).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("shows load errors", async () => {
    mockApi(routes({ [`GET ${base}`]: { status: 500, body: errorBody("INTERNAL", "Down") } }));
    renderApp(page);
    expect(await screen.findByText("Could not load plans")).toBeInTheDocument();
  });
});
