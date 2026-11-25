import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PID, errorBody, expectNoAxeViolations, mockApi, renderApp, shellRoutes } from "../../test/utils";

describe("ProjectsPage", () => {
  it("lists projects with role and stage", async () => {
    mockApi(shellRoutes());
    const { container } = renderApp("/projects");
    expect(await screen.findByRole("link", { name: "Shop" })).toHaveAttribute("href", `/projects/${PID}/setup`);
    expect(screen.getByRole("cell", { name: "QA Lead" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "graph review" })).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("teaches the next step when empty", async () => {
    mockApi({ ...shellRoutes(), "GET /projects": { body: [] } });
    const { container } = renderApp("/projects");
    expect(await screen.findByText("No projects yet")).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("shows a load error", async () => {
    mockApi({ ...shellRoutes(), "GET /projects": { status: 500, body: errorBody("INTERNAL", "Boom") } });
    renderApp("/projects");
    expect(await screen.findByText("Could not load projects")).toBeInTheDocument();
  });

  it("creates a project and opens its setup", async () => {
    const routes = shellRoutes();
    routes["POST /projects"] = {
      status: 201,
      body: { id: PID, name: "Shop", role: "owner", retention_days: 30, stage: null, created_at: "2026-11-20T10:00:00Z" },
    };
    routes[`GET /projects/${PID}/sources`] = { body: { items: [], next_cursor: null } };
    routes[`GET /projects/${PID}/environments`] = { body: [] };
    const calls = mockApi(routes);
    renderApp("/projects");
    await userEvent.type(await screen.findByLabelText("New project name"), "  Shop ");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByRole("heading", { name: "Setup · Shop" })).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST" && c.path === "/projects")!.body).toEqual({ name: "Shop" });
  });

  it("shows why creation failed", async () => {
    mockApi({ ...shellRoutes(), "POST /projects": { status: 400, body: errorBody("VALIDATION_ERROR", "Name too long") } });
    renderApp("/projects");
    await userEvent.type(await screen.findByLabelText("New project name"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByText("Name too long")).toBeInTheDocument();
  });
});
