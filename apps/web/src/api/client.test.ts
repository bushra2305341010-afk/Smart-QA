import { mockApi, errorBody } from "../test/utils";
import { api, ApiError, downloadUrl, readCookie } from "./client";

function setCookie(value: string) {
  document.cookie = `saq_csrf=${value}; path=/`;
}

describe("api client", () => {
  afterEach(() => {
    document.cookie = "saq_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
  });

  it("parses JSON and builds the query string", async () => {
    const calls = mockApi({ "GET /projects/p/sources": { body: { items: [], next_cursor: null } } });
    await expect(api("/projects/p/sources", { query: { limit: 50, cursor: undefined } })).resolves.toEqual({
      items: [],
      next_cursor: null,
    });
    expect(calls[0]!.search.get("limit")).toBe("50");
    expect(calls[0]!.search.has("cursor")).toBe(false);
  });

  it("echoes the CSRF cookie on state-changing requests only", async () => {
    setCookie("tok123");
    const calls = mockApi({ "POST /projects": { status: 201, body: {} }, "GET /me": { body: {} } });
    await api("/projects", { method: "POST", body: { name: "x" } });
    await api("/me");
    expect(calls[0]!.headers.get("X-CSRF-Token")).toBe("tok123");
    expect(calls[0]!.headers.get("Content-Type")).toBe("application/json");
    expect(calls[0]!.body).toEqual({ name: "x" });
    expect(calls[1]!.headers.get("X-CSRF-Token")).toBeNull();
    expect(readCookie("saq_csrf")).toBe("tok123");
  });

  it("turns the error envelope into ApiError", async () => {
    mockApi({
      "POST /projects/p/graph/g/approve": {
        status: 409,
        body: errorBody("GATE_NOT_APPROVED", "2 nodes pending", { pending_node_ids: ["a", "b"] }),
      },
    });
    const err = await api("/projects/p/graph/g/approve", { method: "POST" }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    const e = err as ApiError;
    expect([e.status, e.code, e.message, e.traceId]).toEqual([409, "GATE_NOT_APPROVED", "2 nodes pending", "trace123"]);
    expect(e.details.pending_node_ids).toEqual(["a", "b"]);
  });

  it("handles non-JSON errors and 204", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("boom", { status: 500, statusText: "Server Error" })));
    const err = (await api("/x").catch((e: unknown) => e)) as ApiError;
    expect(err.code).toBe("HTTP_500");
    expect(err.message).toBe("Server Error");
    mockApi({ "POST /auth/logout": { status: 204 } });
    await expect(api("/auth/logout", { method: "POST" })).resolves.toBeUndefined();
  });

  it("refreshes the session once on 401 and retries", async () => {
    let first = true;
    const calls = mockApi({
      "GET /me": () => {
        if (first) {
          first = false;
          return { status: 401, body: errorBody("UNAUTHENTICATED", "Session expired") };
        }
        return { body: { id: "usr_1" } };
      },
      "POST /auth/refresh": { body: { csrf_token: "n" } },
    });
    await expect(api("/me")).resolves.toEqual({ id: "usr_1" });
    expect(calls.map((c) => `${c.method} ${c.path}`)).toEqual(["GET /me", "POST /auth/refresh", "GET /me"]);
  });

  it("does not refresh for the login call itself", async () => {
    const calls = mockApi({ "POST /auth/login": { status: 401, body: errorBody("UNAUTHENTICATED", "Bad password") } });
    await expect(api("/auth/login", { method: "POST", body: {} })).rejects.toThrow("Bad password");
    expect(calls).toHaveLength(1);
  });

  it("sends FormData as multipart without a JSON content type", async () => {
    const calls = mockApi({ "POST /up": { status: 201, body: {} } });
    const form = new FormData();
    form.append("file", new Blob(["x"]), "a.md");
    await api("/up", { method: "POST", body: form });
    expect(calls[0]!.headers.get("Content-Type")).toBeNull();
    expect(downloadUrl("/a")).toBe("/api/v1/a");
  });
});
