import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { caseRow } from "../test/runFixtures";
import { PID, expectNoAxeViolations, renderWith } from "../test/utils";
import { EvidenceDrawer } from "./EvidenceDrawer";

describe("EvidenceDrawer", () => {
  it("lists every evidence kind with sizes and renders SUT text as plain text", async () => {
    const onClose = vi.fn();
    const row = caseRow({
      verdict: "blocked",
      level: "medium",
      blocked: "captcha",
      reason: "<img src=x onerror=alert(1)> blocked",
      failure: { kind: "navigation", message: "", step_n: null },
      evidence: [
        { kind: "screenshot", step_n: null, sha256: "c".repeat(64), size: 10 },
        { kind: "video", step_n: 1, sha256: "d".repeat(64), size: 3 * 1024 * 1024 },
        { kind: "har", step_n: null, sha256: "e".repeat(64), size: 500 },
        { kind: "console", step_n: null, sha256: "f".repeat(64), size: 2048 },
        { kind: "request", step_n: 2, sha256: "1".repeat(64), size: 12 },
        { kind: "other", step_n: 2, sha256: "2".repeat(64), size: 12 },
      ],
    });
    const { container } = renderWith(<EvidenceDrawer pid={PID} row={row} onClose={onClose} />);
    const drawer = screen.getByRole("dialog", { name: /Checkout with one item/ });
    expect(within(drawer).getByRole("status", { name: "Verdict: Blocked, medium confidence" })).toBeInTheDocument();
    expect(within(drawer).getByRole("img", { name: "Screenshot of TC-001 at end of test" })).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: "Video" })).toBeInTheDocument();
    expect(within(drawer).getByText("(step 1, 3.0 MB)")).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: "Network log (HAR)" })).toBeInTheDocument();
    expect(within(drawer).getByText("(end of test, 500 B)")).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: "Console log" })).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: "Request log" })).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: "other" })).toBeInTheDocument();
    expect(within(drawer).getByText("<img src=x onerror=alert(1)> blocked")).toBeInTheDocument();
    expect(within(drawer).getByText("navigation")).toBeInTheDocument();
    expect(within(drawer).queryByText("Message")).not.toBeInTheDocument();
    await expectNoAxeViolations(container);
    await userEvent.keyboard("{Enter}");
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
