import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GV, graph, version } from "../../test/fixtures";
import { PID, errorBody, expectNoAxeViolations, mockApi, renderApp, shellRoutes, type Routes } from "../../test/utils";

const base = `/projects/${PID}/graph`;

function routes(extra: Routes = {}): Routes {
  return {
    ...shellRoutes(),
    [`GET ${base}`]: { body: [version] },
    [`GET ${base}/${GV}`]: { body: graph },
    ...extra,
  };
}

describe("GraphReviewPage (Gate 1)", () => {
  it("shows each node with its exact source quote and location", async () => {
    mockApi(routes());
    const { container } = renderApp(base);
    expect(await screen.findByRole("heading", { name: "Password is 8 to 64 characters" })).toBeInTheDocument();
    expect(screen.getByText("Passwords must be between 8 and 64 characters.")).toBeInTheDocument();
    expect(screen.getByText("prd.pdf · p. 3 · line 12")).toBeInTheDocument();
    expect(screen.getByText("1 of 2 nodes pending")).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("approves a node with the A key and moves to the next", async () => {
    const calls = mockApi(routes({ [`PATCH ${base}/${GV}/nodes/nod_1`]: { body: { ...graph.nodes[0], review_status: "approved" } } }));
    renderApp(base);
    await screen.findByRole("heading", { name: "Password is 8 to 64 characters" });
    await userEvent.keyboard("a");
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({ review_status: "approved" });
    expect(await screen.findByRole("heading", { name: "Checkout" })).toBeInTheDocument();
  });

  it("moves with J/K and rejects with R", async () => {
    const calls = mockApi(routes({ [`PATCH ${base}/${GV}/nodes/nod_2`]: { body: graph.nodes[1] } }));
    renderApp(base);
    await screen.findByRole("heading", { name: "Password is 8 to 64 characters" });
    await userEvent.keyboard("j");
    expect(screen.getByRole("heading", { name: "Checkout" })).toBeInTheDocument();
    expect(screen.getByText("This node has no citation.", { exact: false })).toBeInTheDocument();
    await userEvent.keyboard("k");
    expect(screen.getByRole("heading", { name: "Password is 8 to 64 characters" })).toBeInTheDocument();
    await userEvent.keyboard("j");
    await userEvent.keyboard("r");
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ review_status: "rejected" }));
  });

  it("edits a node label", async () => {
    const calls = mockApi(routes({ [`PATCH ${base}/${GV}/nodes/nod_1`]: { body: graph.nodes[0] } }));
    renderApp(base);
    await userEvent.click(await screen.findByRole("button", { name: "Edit label" }));
    const input = screen.getByLabelText("Corrected label");
    await userEvent.clear(input);
    await userEvent.type(input, "Password is 8 to 72 characters");
    await userEvent.click(screen.getByRole("button", { name: "Save edit" }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ review_status: "edited", label: "Password is 8 to 72 characters" }),
    );
  });

  it("filters by node type", async () => {
    mockApi(routes());
    renderApp(base);
    await screen.findByRole("heading", { name: "Password is 8 to 64 characters" });
    await userEvent.selectOptions(screen.getByLabelText("Node type"), "Journey");
    expect(screen.getByRole("heading", { name: "Checkout" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem").filter((li) => li.closest('[aria-label="Graph nodes"]'))).toHaveLength(1);
  });

  it("shows the server's refusal while nodes are pending", async () => {
    mockApi(
      routes({
        [`POST ${base}/${GV}/approve`]: {
          status: 409,
          body: errorBody("GATE_NOT_APPROVED", "1 node is still pending", { gate: 1, pending_node_ids: ["nod_1"] }),
        },
      }),
    );
    renderApp(base);
    await userEvent.click(await screen.findByRole("button", { name: "Approve graph" }));
    expect(await screen.findByText("1 nodes still need a decision")).toBeInTheDocument();
    expect(screen.getByText(/1 node is still pending/)).toBeInTheDocument();
  });

  it("approves the graph", async () => {
    mockApi(routes({ [`POST ${base}/${GV}/approve`]: { body: { ...version, status: "approved", pending: 0 } } }));
    renderApp(base);
    await userEvent.click(await screen.findByRole("button", { name: "Approve graph" }));
    expect(await screen.findByText("Graph approved. Planning starts next.")).toBeInTheDocument();
  });

  it("rejects the whole graph through the pipeline", async () => {
    const calls = mockApi(routes({ [`POST /projects/${PID}/pipeline/events`]: { body: { stage: "understand", status: "queued", entered_at: "" } } }));
    renderApp(base);
    await userEvent.click(await screen.findByRole("button", { name: "Reject graph and rebuild" }));
    await waitFor(() => expect(calls.find((c) => c.path.endsWith("/pipeline/events"))?.body).toEqual({ event: "graph_rejected" }));
  });

  it("is read-only for an approved version", async () => {
    const approved = { ...version, status: "approved" };
    mockApi(routes({ [`GET ${base}`]: { body: [approved] }, [`GET ${base}/${GV}`]: { body: { ...graph, version: approved } } }));
    renderApp(base);
    expect(await screen.findByText("This version is approved; it cannot be changed.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve node" })).toBeNull();
  });

  it("teaches the next step when there is no graph", async () => {
    mockApi(routes({ [`GET ${base}`]: { body: [] } }));
    const { container } = renderApp(base);
    expect(await screen.findByText("No graph yet")).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("shows load errors", async () => {
    mockApi(routes({ [`GET ${base}`]: { status: 500, body: errorBody("INTERNAL", "Down") } }));
    renderApp(base);
    expect(await screen.findByText("Could not load the graph")).toBeInTheDocument();
  });
});
