import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { draftBug } from "../../test/fixtures";
import { PID, errorBody, expectNoAxeViolations, mockApi, renderApp, shellRoutes, type Routes } from "../../test/utils";

const base = `/projects/${PID}/bugs`;

function routes(extra: Routes = {}): Routes {
  return {
    ...shellRoutes(),
    [`GET ${base}`]: { body: [draftBug] },
    [`GET ${base}/bug_1/duplicates`]: { body: [] },
    ...extra,
  };
}

describe("BugReviewPage (Gate 4)", () => {
  it("shows a draft as plain text and keeps filing closed while drafts remain", async () => {
    mockApi(routes());
    const { container } = renderApp(base);
    expect(await screen.findByRole("heading", { name: "Pay button does nothing" })).toBeInTheDocument();
    expect(screen.getByLabelText("Report (Markdown, shown as plain text)")).toHaveValue(draftBug.body_md);
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByRole("button", { name: "Confirm & file" })).toBeDisabled();
    expect(await screen.findByText("No similar issues found.")).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("warns about duplicates before filing", async () => {
    mockApi(routes({ [`GET ${base}/bug_1/duplicates`]: { body: [{ source: "tracker", title: "Pay broken", ref: "#12" }] } }));
    renderApp(base);
    expect(await screen.findByText("Possible duplicates")).toBeInTheDocument();
    expect(screen.getByText("Pay broken")).toBeInTheDocument();
  });

  it("reports a failing duplicate check", async () => {
    mockApi(routes({ [`GET ${base}/bug_1/duplicates`]: { status: 502, body: errorBody("UPSTREAM_ERROR", "Tracker down") } }));
    renderApp(base);
    expect(await screen.findByText("Tracker down")).toBeInTheDocument();
  });

  it("confirms a draft", async () => {
    const calls = mockApi(routes({ [`POST ${base}/bug_1/confirm`]: { body: { ...draftBug, status: "confirmed" } } }));
    renderApp(base);
    await userEvent.click(await screen.findByRole("button", { name: "Confirm bug" }));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/bug_1/confirm"))).toBe(true));
  });

  it("dismisses a draft with a reason", async () => {
    const calls = mockApi(routes({ [`POST ${base}/bug_1/dismiss`]: { body: { ...draftBug, status: "dismissed" } } }));
    renderApp(base);
    await userEvent.type(await screen.findByLabelText("Dismiss reason (teaches the judge)"), "expected behaviour");
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    await waitFor(() => expect(calls.find((c) => c.path.endsWith("/dismiss"))?.body).toEqual({ reason: "expected behaviour" }));
  });

  it("edits a draft and requires saving before confirming", async () => {
    const calls = mockApi(routes({ [`PATCH ${base}/bug_1`]: { body: draftBug } }));
    renderApp(base);
    const title = await screen.findByLabelText("Title");
    await userEvent.type(title, "!");
    await userEvent.selectOptions(screen.getByLabelText("Severity"), "critical");
    expect(screen.getByRole("button", { name: "Confirm bug" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({
        title: "Pay button does nothing!",
        severity: "critical",
        body_md: draftBug.body_md,
      }),
    );
  });

  it("files once every draft is decided", async () => {
    const confirmed = { ...draftBug, status: "confirmed" };
    const calls = mockApi(routes({ [`GET ${base}`]: { body: [confirmed] }, [`POST ${base}/approve`]: { body: { stage: "report", status: "queued" } } }));
    renderApp(base);
    expect(await screen.findByText(/\*\*Steps\*\*/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Confirm & file" }));
    expect(await screen.findByText(/Gate 4 approved/)).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST" && c.path === `${base}/approve`)).toBe(true);
  });

  it("shows the gate refusal", async () => {
    mockApi(
      routes({
        [`GET ${base}`]: { body: [{ ...draftBug, status: "confirmed" }] },
        [`POST ${base}/approve`]: { status: 409, body: errorBody("STATE_CONFLICT", "Not at bug review") },
      }),
    );
    renderApp(base);
    await userEvent.click(await screen.findByRole("button", { name: "Confirm & file" }));
    expect(await screen.findByText("Not at bug review")).toBeInTheDocument();
  });

  it("shows empty and error states", async () => {
    mockApi(routes({ [`GET ${base}`]: { body: [] } }));
    const { container, unmount } = renderApp(base);
    expect(await screen.findByText("No bug drafts")).toBeInTheDocument();
    await expectNoAxeViolations(container);
    unmount();
    mockApi(routes({ [`GET ${base}`]: { status: 500, body: errorBody("INTERNAL", "Down") } }));
    renderApp(base);
    expect(await screen.findByText("Could not load bugs")).toBeInTheDocument();
  });
});
