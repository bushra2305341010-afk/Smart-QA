import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { uvCase, verifiedCase } from "../../test/fixtures";
import { PID, errorBody, expectNoAxeViolations, mockApi, renderApp, shellRoutes, type Routes } from "../../test/utils";

const base = `/projects/${PID}/cases`;

function routes(extra: Routes = {}): Routes {
  return { ...shellRoutes(), [`GET ${base}`]: { body: { items: [verifiedCase, uvCase], next_cursor: null } }, ...extra };
}

describe("CaseReviewPage (Gate 3)", () => {
  it("opens Unable-to-Verify cases first and does not let them be approved", async () => {
    const calls = mockApi(routes());
    const { container } = renderApp(base);
    expect(await screen.findByRole("heading", { name: "Checkout shows a discount" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Verdict: Unable to Verify" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve case" })).toBeDisabled();
    expect(screen.getByText(/the quote was not found in the source/)).toBeInTheDocument();
    expect(screen.getByText("Why unverified: quote not found")).toBeInTheDocument();
    await userEvent.keyboard("a");
    expect(calls.some((c) => c.path.endsWith("/cases/review"))).toBe(false);
    await expectNoAxeViolations(container);
  });

  it("shows expected result with its quote, steps and data", async () => {
    mockApi(routes());
    renderApp(base);
    await screen.findByRole("heading", { name: "Checkout shows a discount" });
    await userEvent.keyboard("j");
    expect(screen.getByRole("heading", { name: "Checkout with one item" })).toBeInTheDocument();
    expect(screen.getByText("Order confirmation is shown")).toBeInTheDocument();
    expect(screen.getByText("After payment the order confirmation page is shown.")).toBeInTheDocument();
    expect(screen.getByText("Press Pay")).toBeInTheDocument();
    expect(screen.getByText("Cart has one item")).toBeInTheDocument();
    expect(screen.getByText("qty")).toBeInTheDocument();
  });

  it("approves a verified case with A and opens the next", async () => {
    const calls = mockApi(routes({ [`POST ${base}/review`]: { body: { updated: 1 } } }));
    renderApp(base);
    await screen.findByRole("heading", { name: "Checkout shows a discount" });
    await userEvent.click(screen.getByRole("button", { name: /Checkout with one item/ }));
    await userEvent.keyboard("a");
    await waitFor(() => expect(calls.find((c) => c.path.endsWith("/cases/review"))?.body).toEqual({ case_ids: ["tc_1"], decision: "approved" }));
  });

  it("rejects an unverified case", async () => {
    const calls = mockApi(routes({ [`POST ${base}/review`]: { body: { updated: 1 } } }));
    renderApp(base);
    await userEvent.click(await screen.findByRole("button", { name: "Reject case" }));
    await waitFor(() => expect(calls.find((c) => c.path.endsWith("/cases/review"))?.body).toEqual({ case_ids: ["tc_2"], decision: "rejected" }));
  });

  it("shows the server's citation refusal", async () => {
    mockApi(routes({ [`POST ${base}/review`]: { status: 422, body: errorBody("CITATION_UNVERIFIED", "No verified source") } }));
    renderApp(base);
    await screen.findByRole("heading", { name: "Checkout shows a discount" });
    await userEvent.keyboard("j");
    await userEvent.click(screen.getByRole("button", { name: "Approve case" }));
    expect(await screen.findByText("No verified source")).toBeInTheDocument();
  });

  it("finishes Gate 3 only when nothing is pending", async () => {
    const done = [{ ...verifiedCase, review_status: "approved" }, { ...uvCase, review_status: "rejected" }];
    mockApi(routes({ [`GET ${base}`]: { body: { items: done, next_cursor: null } }, [`POST ${base}/approve`]: { body: { stage: "compile", status: "queued" } } }));
    renderApp(base);
    const finish = await screen.findByRole("button", { name: "Finish review (Gate 3)" });
    expect(finish).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Approve case" })).toBeNull();
    await userEvent.click(finish);
    expect(await screen.findByText("Cases approved. They will be compiled and run next.")).toBeInTheDocument();
  });

  it("keeps Gate 3 closed while cases are pending", async () => {
    mockApi(routes());
    renderApp(base);
    expect(await screen.findByRole("button", { name: "Finish review (Gate 3)" })).toBeDisabled();
    expect(screen.getByText("2 pending · 1 Unable to Verify · 2 cases")).toBeInTheDocument();
  });

  it("shows empty and error states", async () => {
    mockApi(routes({ [`GET ${base}`]: { body: { items: [], next_cursor: null } } }));
    const { container, unmount } = renderApp(base);
    expect(await screen.findByText("No test cases yet")).toBeInTheDocument();
    await expectNoAxeViolations(container);
    unmount();
    mockApi(routes({ [`GET ${base}`]: { status: 500, body: errorBody("INTERNAL", "Down") } }));
    renderApp(base);
    expect(await screen.findByText("Could not load test cases")).toBeInTheDocument();
  });
});
