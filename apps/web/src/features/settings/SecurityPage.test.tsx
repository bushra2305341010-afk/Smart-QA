import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { errorBody, expectNoAxeViolations, mockApi, renderApp, shellRoutes } from "../../test/utils";

describe("SecurityPage", () => {
  it("sets up and turns on two-factor", async () => {
    const calls = mockApi({
      ...shellRoutes(),
      "POST /auth/totp/setup": { body: { secret: "JBSWY3DP", otpauth_uri: "otpauth://totp/SmartQA:a?secret=JBSWY3DP" } },
      "POST /auth/totp/enable": (c) =>
        (c.body as { code: string }).code === "123456"
          ? { status: 204 }
          : { status: 400, body: errorBody("INVALID_CODE", "Wrong code") },
    });
    const { container } = renderApp("/settings/security");
    await userEvent.click(await screen.findByRole("button", { name: "Set up two-factor" }));
    expect(await screen.findByText("JBSWY3DP")).toBeInTheDocument();
    await expectNoAxeViolations(container);
    const input = screen.getByLabelText("Code from the app");
    await userEvent.type(input, "111111");
    await userEvent.click(screen.getByRole("button", { name: "Turn on two-factor" }));
    expect(await screen.findByText("Wrong code")).toBeInTheDocument();
    await userEvent.clear(input);
    await userEvent.type(input, "123456");
    await userEvent.click(screen.getByRole("button", { name: "Turn on two-factor" }));
    expect(await screen.findByText(/Two-factor sign-in is on/)).toBeInTheDocument();
    expect(calls.filter((c) => c.path === "/auth/totp/enable")).toHaveLength(2);
  });

  it("explains when the server cannot do two-factor", async () => {
    mockApi({
      ...shellRoutes(),
      "POST /auth/totp/setup": { status: 503, body: errorBody("UNAVAILABLE", "Set SAQ_ENCRYPTION_KEY to use two-factor sign-in") },
    });
    renderApp("/settings/security");
    await userEvent.click(await screen.findByRole("button", { name: "Set up two-factor" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("SAQ_ENCRYPTION_KEY");
  });
});
