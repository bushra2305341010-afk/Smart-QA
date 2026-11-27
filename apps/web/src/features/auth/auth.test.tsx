import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { errorBody, expectNoAxeViolations, mockApi, renderApp, shellRoutes } from "../../test/utils";

const signedOut = { "GET /me": { status: 401, body: errorBody("UNAUTHENTICATED", "Sign in required") } };

async function fillLogin() {
  await userEvent.type(await screen.findByLabelText("Email"), "lead@example.com");
  await userEvent.type(screen.getByLabelText("Password"), "correct horse battery");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("LoginPage", () => {
  it("has no axe violations", async () => {
    mockApi(signedOut);
    const { container } = renderApp("/login");
    await screen.findByRole("heading", { name: "Sign in" });
    await expectNoAxeViolations(container);
  });

  it("signs in with a password and opens projects", async () => {
    let signedIn = false;
    const shell = shellRoutes();
    const calls = mockApi({
      ...shell,
      "GET /me": () => (signedIn ? { body: { id: "usr_1", email: "lead@example.com", memberships: [] } } : signedOut["GET /me"]),
      "POST /auth/login": () => {
        signedIn = true;
        return { body: { user: { id: "usr_1", email: "lead@example.com" }, csrf_token: "c" } };
      },
    });
    renderApp("/login");
    await fillLogin();
    expect(await screen.findByRole("heading", { name: "Projects" })).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/auth/login")!.body).toEqual({
      email: "lead@example.com",
      password: "correct horse battery",
    });
  });

  it("asks for a TOTP code when two-factor is on", async () => {
    let signedIn = false;
    const calls = mockApi({
      ...shellRoutes(),
      "GET /me": () => (signedIn ? { body: { id: "usr_1", email: "a@b.c", memberships: [] } } : signedOut["GET /me"]),
      "POST /auth/login": { body: { mfa_required: true, mfa_token: "mfa-tok" } },
      "POST /auth/login/mfa": (c) => {
        if ((c.body as { code: string }).code !== "123456") {
          return { status: 400, body: errorBody("INVALID_CODE", "Wrong or reused code") };
        }
        signedIn = true;
        return { body: { user: { id: "usr_1", email: "a@b.c" }, csrf_token: "c" } };
      },
    });
    const { container } = renderApp("/login");
    await fillLogin();
    const code = await screen.findByLabelText("Authentication code");
    await expectNoAxeViolations(container);
    await userEvent.type(code, "000000");
    await userEvent.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByText("Wrong or reused code")).toBeInTheDocument();
    await userEvent.clear(code);
    await userEvent.type(code, "123456");
    await userEvent.click(screen.getByRole("button", { name: "Verify" }));
    expect(await screen.findByRole("heading", { name: "Projects" })).toBeInTheDocument();
    expect(calls.filter((c) => c.path === "/auth/login/mfa").at(-1)!.body).toEqual({ mfa_token: "mfa-tok", code: "123456" });
  });

  it("can go back from the code step", async () => {
    mockApi({ ...signedOut, "POST /auth/login": { body: { mfa_required: true, mfa_token: "t" } } });
    renderApp("/login");
    await fillLogin();
    await userEvent.click(await screen.findByRole("button", { name: "Back" }));
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("shows why sign-in failed", async () => {
    mockApi({ ...signedOut, "POST /auth/login": { status: 401, body: errorBody("UNAUTHENTICATED", "Wrong email or password") } });
    renderApp("/login");
    await fillLogin();
    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong email or password");
  });
});

describe("RegisterPage", () => {
  it("creates an account and returns to sign-in", async () => {
    const calls = mockApi({ ...signedOut, "POST /auth/register": { status: 201, body: { id: "usr_1", email: "n@x.io" } } });
    const { container } = renderApp("/register");
    await screen.findByRole("heading", { name: "Create account" });
    await expectNoAxeViolations(container);
    await userEvent.type(screen.getByLabelText("Email"), "n@x.io");
    await userEvent.type(screen.getByLabelText("Password"), "a long passphrase");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Account created. Sign in to continue.")).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/auth/register")!.body).toEqual({ email: "n@x.io", password: "a long passphrase" });
  });

  it("shows a taken email", async () => {
    mockApi({ ...signedOut, "POST /auth/register": { status: 409, body: errorBody("EMAIL_TAKEN", "Email already registered") } });
    renderApp("/register");
    await userEvent.type(await screen.findByLabelText("Email"), "n@x.io");
    await userEvent.type(screen.getByLabelText("Password"), "pw");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email already registered");
  });
});
