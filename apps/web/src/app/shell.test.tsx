import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";
import { PID, errorBody, expectNoAxeViolations, mockApi, renderApp, shellRoutes } from "../test/utils";

describe("app shell", () => {
  it("sends signed-out users to the login screen", async () => {
    mockApi({ "GET /me": { status: 401, body: errorBody("UNAUTHENTICATED", "Sign in required") } });
    renderApp(`/projects/${PID}/graph`);
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("returns to the requested screen after signing in", async () => {
    let signedIn = false;
    mockApi({
      ...shellRoutes(),
      "GET /me": () =>
        signedIn
          ? { body: { id: "usr_1", email: "lead@example.com", memberships: [] } }
          : { status: 401, body: errorBody("UNAUTHENTICATED", "Sign in required") },
      "POST /auth/login": () => {
        signedIn = true;
        return { body: { user: { id: "usr_1", email: "lead@example.com" }, csrf_token: "c" } };
      },
    });
    renderApp(`/projects/${PID}/runs`);
    await userEvent.type(await screen.findByLabelText("Email"), "lead@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "pw");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { name: "Runs" })).toBeInTheDocument();
  });

  it("shows an error when the session check fails for another reason", async () => {
    mockApi({ "GET /me": { status: 503, body: errorBody("UNAVAILABLE", "Database is not configured") } });
    renderApp("/projects");
    expect(await screen.findByText("Database is not configured")).toBeInTheDocument();
  });

  it("renders nav rail, switcher, stepper and cost meter inside a project", async () => {
    mockApi(shellRoutes());
    const { container } = renderApp(`/projects/${PID}/runs`);
    expect(await screen.findByRole("heading", { name: "Runs" })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(nav).toHaveTextContent("Graph");
    expect(screen.getByRole("link", { name: /Runs/ })).toHaveAttribute("aria-current", "page");
    expect(await screen.findByRole("meter")).toBeInTheDocument();
    expect(await screen.findByText("Understand")).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "Shop" })).toBeInTheDocument();
    expect(screen.getByLabelText("Project")).toHaveValue(PID);
    expect(await screen.findByText("lead@example.com")).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("switches project while keeping the screen", async () => {
    const other = "prj_" + "b".repeat(32);
    const routes = shellRoutes();
    routes["GET /projects"] = {
      body: [
        { id: PID, name: "Shop", role: "owner", retention_days: 30, stage: null, created_at: "2026-11-20T10:00:00Z" },
        { id: other, name: "Blog", role: "viewer", retention_days: 30, stage: null, created_at: "2026-11-20T10:00:00Z" },
      ],
    };
    routes[`GET /projects/${other}/pipeline`] = { body: { current: null, history: [] } };
    mockApi(routes);
    renderApp(`/projects/${PID}/runs`);
    await screen.findByRole("option", { name: "Blog" });
    await userEvent.selectOptions(screen.getByLabelText("Project"), other);
    await waitFor(() => expect(screen.getByLabelText("Project")).toHaveValue(other));
    expect(screen.getByRole("heading", { name: "Runs" })).toBeInTheDocument();
  });

  it("signs out and returns to login", async () => {
    const routes = shellRoutes();
    routes["POST /auth/logout"] = { status: 204 };
    const calls = mockApi(routes);
    renderApp("/projects");
    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/auth/logout")).toBe(true);
  });

  it("applies the chosen theme to the document", async () => {
    mockApi(shellRoutes());
    renderApp("/projects");
    const select = await screen.findByLabelText("Colour theme");
    await userEvent.selectOptions(select, "dark");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    await userEvent.selectOptions(select, "system");
    expect(document.documentElement).not.toHaveAttribute("data-theme");
  });

  it("shows a not-found page for unknown addresses", async () => {
    mockApi(shellRoutes());
    const { container } = renderApp("/nowhere");
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("boots the real App with its own router", async () => {
    mockApi({ "GET /me": { status: 401, body: errorBody("UNAUTHENTICATED", "x") } });
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });
});
