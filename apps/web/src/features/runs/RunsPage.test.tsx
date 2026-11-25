import { screen } from "@testing-library/react";
import { PID, expectNoAxeViolations, mockApi, renderApp, shellRoutes } from "../../test/utils";

describe("RunsPage placeholder", () => {
  it("is routed and shows an empty state", async () => {
    mockApi(shellRoutes());
    const { container } = renderApp(`/projects/${PID}/runs`);
    expect(await screen.findByRole("heading", { name: "Runs" })).toBeInTheDocument();
    expect(screen.getByText("Run dashboard coming soon")).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });
});
