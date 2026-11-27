import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RUN } from "../../test/fixtures";
import { runSummary } from "../../test/runFixtures";
import { PID, errorBody, expectNoAxeViolations, mockApi, renderApp, shellRoutes } from "../../test/utils";

const page = `/projects/${PID}/reports`;

describe("ReportsPage", () => {
  it("offers the workbook and evidence pack for every listed run", async () => {
    mockApi({ ...shellRoutes(), [`GET /projects/${PID}/runs`]: { body: { items: [runSummary], next_cursor: null } } });
    const { container } = renderApp(page);
    const xlsx = await screen.findByRole("link", { name: `Excel workbook for ${RUN}` });
    expect(xlsx).toHaveAttribute("href", `/api/v1/projects/${PID}/runs/${RUN}/export.xlsx`);
    expect(screen.getByRole("link", { name: `Evidence pack for ${RUN}` })).toHaveAttribute(
      "href",
      `/api/v1/projects/${PID}/runs/${RUN}/evidence-pack`,
    );
    expect(screen.getAllByRole("link", { name: /Excel workbook/ })).toHaveLength(1);
    expect(screen.getByRole("link", { name: RUN })).toHaveAttribute("href", `/projects/${PID}/runs/${RUN}`);
    expect(screen.getByRole("link", { name: "Runs dashboard" })).toHaveAttribute("href", `/projects/${PID}/runs`);
    await expectNoAxeViolations(container);
  });

  it("accepts a typed run id and rejects malformed ones", async () => {
    mockApi({ ...shellRoutes(), [`GET /projects/${PID}/runs`]: { body: { items: [], next_cursor: null } } });
    const { container } = renderApp(page);
    expect(await screen.findByText("No runs yet")).toBeInTheDocument();
    await expectNoAxeViolations(container);
    const input = screen.getByLabelText("Run ID");
    await userEvent.type(input, "run_bad");
    expect(screen.getByRole("button", { name: "Add run" })).toBeDisabled();
    await userEvent.clear(input);
    await userEvent.type(input, RUN);
    await userEvent.click(screen.getByRole("button", { name: "Add run" }));
    expect(screen.getByRole("link", { name: `Excel workbook for ${RUN}` })).toBeInTheDocument();
  });

  it("shows a load error", async () => {
    mockApi({ ...shellRoutes(), [`GET /projects/${PID}/runs`]: { status: 500, body: errorBody("INTERNAL", "Down") } });
    renderApp(page);
    expect(await screen.findByText("Could not load runs")).toBeInTheDocument();
  });
});
