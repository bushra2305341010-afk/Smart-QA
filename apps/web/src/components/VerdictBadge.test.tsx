import { render, screen } from "@testing-library/react";
import { expectNoAxeViolations } from "../test/utils";
import { VerdictBadge, type Verdict } from "./VerdictBadge";

describe("VerdictBadge", () => {
  it("shows label and icon, not colour alone", () => {
    render(<VerdictBadge verdict="fail" />);
    expect(screen.getByRole("status")).toHaveTextContent("✕Fail");
  });

  it("announces confidence to screen readers", () => {
    render(<VerdictBadge verdict="pass" confidence="high" />);
    expect(screen.getByRole("status")).toHaveAccessibleName("Verdict: Pass, high confidence");
  });

  it("supports Unable to Verify", () => {
    render(<VerdictBadge verdict="unable_to_verify" />);
    expect(screen.getByText("Unable to Verify")).toBeInTheDocument();
  });

  it("has no axe violations for any verdict", async () => {
    const all: Verdict[] = ["pass", "fail", "flaky", "blocked", "test_error", "unable_to_verify"];
    const { container } = render(
      <div>
        {all.map((v) => (
          <VerdictBadge key={v} verdict={v} confidence="low" />
        ))}
      </div>,
    );
    await expectNoAxeViolations(container);
  });
});
