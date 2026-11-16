import { render, screen } from "@testing-library/react";
import { VerdictBadge } from "./VerdictBadge";

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
});
