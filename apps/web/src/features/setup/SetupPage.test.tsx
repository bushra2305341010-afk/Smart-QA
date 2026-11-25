import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PID, errorBody, expectNoAxeViolations, mockApi, renderApp, shellRoutes, type Routes } from "../../test/utils";

const source = {
  id: "src_1",
  kind: "pdf",
  uri: "s3://b/prd.pdf",
  sha256: "ab",
  status: "parsed",
  filename: "prd.pdf",
  size: 2048,
  error: null,
  created_at: "2026-11-20T10:00:00Z",
};

function routes(extra: Routes = {}): Routes {
  return {
    ...shellRoutes(),
    [`GET /projects/${PID}/sources`]: { body: { items: [source], next_cursor: null } },
    [`GET /projects/${PID}/environments`]: {
      body: [{ id: "env_1", name: "Staging", kind: "staging", base_url: "https://staging.shop.test", allowed_hosts: ["staging.shop.test"], safe_actions: {} }],
    },
    ...extra,
  };
}

describe("SetupPage", () => {
  it("lists sources, environments and the pipeline state", async () => {
    mockApi(routes());
    const view = renderApp(`/projects/${PID}/setup`);
    expect(await view.findByText("prd.pdf")).toBeInTheDocument();
    expect(view.getByText("2 KB")).toBeInTheDocument();
    expect(await view.findByText("https://staging.shop.test")).toBeInTheDocument();
    expect(await view.findByText("Stage: graph review · awaiting approval")).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Cancel pipeline" })).toBeInTheDocument();
    await expectNoAxeViolations(view.container);
  });

  it("shows empty states and starts the pipeline", async () => {
    const calls = mockApi(
      routes({
        [`GET /projects/${PID}/sources`]: { body: { items: [], next_cursor: null } },
        [`GET /projects/${PID}/environments`]: { body: [] },
        [`GET /projects/${PID}/pipeline`]: { body: { current: null, history: [] } },
        [`POST /projects/${PID}/pipeline/events`]: { body: { stage: "ingest", status: "queued", entered_at: "" } },
      }),
    );
    const view = renderApp(`/projects/${PID}/setup`);
    expect(await view.findByText("No sources yet")).toBeInTheDocument();
    expect(await view.findByText("No environments yet")).toBeInTheDocument();
    await expectNoAxeViolations(view.container);
    await userEvent.click(await screen.findByRole("button", { name: "Start pipeline" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/pipeline/events"))).toBe(true));
    expect(calls.find((c) => c.path.endsWith("/pipeline/events"))!.body).toEqual({ event: "start" });
  });

  it("retries a failed stage and shows refusals", async () => {
    mockApi(
      routes({
        [`GET /projects/${PID}/pipeline`]: { body: { current: { stage: "understand", status: "failed", entered_at: "" }, history: [] } },
        [`POST /projects/${PID}/pipeline/events`]: { status: 402, body: errorBody("BUDGET_EXCEEDED", "Budget cap reached") },
      }),
    );
    renderApp(`/projects/${PID}/setup`);
    await userEvent.click(await screen.findByRole("button", { name: "Retry stage" }));
    expect(await screen.findByText("Budget cap reached")).toBeInTheDocument();
  });

  it("uploads a document as multipart", async () => {
    const calls = mockApi(routes({ [`POST /projects/${PID}/sources/upload`]: { status: 201, body: source } }));
    renderApp(`/projects/${PID}/setup`);
    const file = new File(["# PRD"], "prd.md", { type: "text/markdown" });
    await userEvent.upload(await screen.findByLabelText("Upload a document"), file);
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/sources/upload"))).toBe(true));
    const body = calls.find((c) => c.path.endsWith("/sources/upload"))!.body as FormData;
    expect((body.get("file") as File).name).toBe("prd.md");
  });

  it("shows an upload refusal", async () => {
    mockApi(routes({ [`POST /projects/${PID}/sources/upload`]: { status: 415, body: errorBody("UNSUPPORTED_TYPE", "Unsupported file type") } }));
    renderApp(`/projects/${PID}/setup`);
    await userEvent.upload(await screen.findByLabelText("Upload a document"), new File(["x"], "a.pdf", { type: "application/pdf" }));
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByText("Unsupported file type")).toBeInTheDocument();
  });

  it("connects a Git repository", async () => {
    const calls = mockApi(routes({ [`POST /projects/${PID}/sources/repo`]: { status: 201, body: source } }));
    renderApp(`/projects/${PID}/setup`);
    await userEvent.type(await screen.findByLabelText("Git repository (https, read-only)"), "https://github.com/org/shop");
    await userEvent.type(screen.getByLabelText("Branch or tag (optional)"), "main");
    await userEvent.click(screen.getByRole("button", { name: "Connect repository" }));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/sources/repo"))).toBe(true));
    expect(calls.find((c) => c.path.endsWith("/sources/repo"))!.body).toEqual({ url: "https://github.com/org/shop", ref: "main" });
  });

  it("adds an environment and warns about production", async () => {
    const calls = mockApi(
      routes({
        [`POST /projects/${PID}/environments`]: { status: 403, body: errorBody("FORBIDDEN", "Your role lacks this permission") },
      }),
    );
    renderApp(`/projects/${PID}/setup`);
    await userEvent.type(await screen.findByLabelText("Name"), "Prod");
    await userEvent.selectOptions(screen.getByLabelText("Kind"), "production");
    expect(screen.getByText(/Production environments need the Owner role/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Base URL"), "https://shop.test");
    await userEvent.click(screen.getByRole("button", { name: "Add environment" }));
    expect(await screen.findByText("Your role lacks this permission")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST" && c.path.endsWith("/environments"))!.body).toEqual({
      name: "Prod",
      kind: "production",
      base_url: "https://shop.test",
    });
  });

  it("shows when the project cannot be opened", async () => {
    mockApi(routes({ [`GET /projects/${PID}`]: { status: 404, body: errorBody("NOT_FOUND", "Project not found") } }));
    renderApp(`/projects/${PID}/setup`);
    expect(await screen.findByText("Project not found")).toBeInTheDocument();
  });
});
