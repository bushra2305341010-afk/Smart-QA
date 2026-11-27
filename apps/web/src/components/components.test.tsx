import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../api/client";
import { expectNoAxeViolations } from "../test/utils";
import { CitationQuote } from "./CitationQuote";
import { CostMeter } from "./CostMeter";
import { PageHeader } from "./PageHeader";
import { StageStepper } from "./StageStepper";
import { StatusBadge } from "./StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "./States";

describe("CitationQuote", () => {
  it("shows a verified quote with its location as plain text", async () => {
    const { container } = render(
      <CitationQuote quote={"<b>8 to 64</b> characters"} status="verified" file="prd.pdf" page={3} line={12} />,
    );
    expect(screen.getByText("AI · cited")).toBeInTheDocument();
    expect(screen.getByText("prd.pdf · p. 3 · line 12")).toBeInTheDocument();
    expect(screen.getByText("<b>8 to 64</b> characters")).toBeInTheDocument();
    expect(container.querySelector("b")).toBeNull();
    await expectNoAxeViolations(container);
  });

  it("labels unverified quotes and gives the reason", () => {
    render(<CitationQuote quote={null} status="unable_to_verify" reason="quote not found" />);
    expect(screen.getByText("AI · unverified")).toBeInTheDocument();
    expect(screen.getByText("No source quote.")).toBeInTheDocument();
    expect(screen.getByText("Why unverified: quote not found")).toBeInTheDocument();
  });
});

describe("StageStepper", () => {
  it("marks the current step and locked gates", async () => {
    const { container } = render(
      <StageStepper current={{ stage: "plan_approval", status: "awaiting_approval", entered_at: "" }} />,
    );
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(6);
    expect(items[2]).toHaveAttribute("aria-current", "step");
    expect(items[2]).toHaveTextContent("Plan: awaiting approval, gate 2 not approved");
    expect(items[1]).toHaveTextContent("Understand: done");
    expect(items[3]).toHaveTextContent("Design: not started, gate 3 not approved");
    await expectNoAxeViolations(container);
  });

  it("says when the pipeline has not started, and when it is done", () => {
    const { rerender } = render(<StageStepper current={null} />);
    expect(screen.getByText("Pipeline not started.")).toBeInTheDocument();
    rerender(<StageStepper current={{ stage: "done", status: "done", entered_at: "" }} />);
    expect(screen.getAllByRole("listitem").every((li) => li.textContent?.includes("done"))).toBe(true);
  });
});

describe("CostMeter", () => {
  it("exposes spend as an accessible meter", async () => {
    const { container } = render(<CostMeter spent="9.50" cap="10" />);
    const meter = screen.getByRole("meter", { name: "Model spend this month: $9.50 of $10.00" });
    expect(meter).toHaveAttribute("aria-valuenow", "95");
    await expectNoAxeViolations(container);
  });

  it("handles a zero cap", () => {
    render(<CostMeter spent="0" cap="0" />);
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuenow", "0");
  });
});

describe("States", () => {
  it("renders loading, empty and error with trace id copy", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    const err = new ApiError(409, { code: "STATE_CONFLICT", message: "Wrong stage", details: {}, trace_id: "t1" });
    const { container } = render(
      <div>
        <LoadingState />
        <EmptyState title="Nothing">Do this next</EmptyState>
        <ErrorState error={err} />
      </div>,
    );
    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(screen.getByText("Do this next")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Wrong stage (STATE_CONFLICT)");
    await expectNoAxeViolations(container);
    await userEvent.click(screen.getByRole("button", { name: "Copy" }));
    expect(writeText).toHaveBeenCalledWith("t1");
    expect(await screen.findByRole("button", { name: "Copied" })).toBeInTheDocument();
  });

  it("shows plain errors without a trace id", () => {
    render(<ErrorState error={new Error("offline")} title="Oops" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Oopsoffline");
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("axe helper", () => {
  it("fails on a real violation (an unlabelled input)", async () => {
    const { container } = render(<input type="text" />);
    await expect(expectNoAxeViolations(container)).rejects.toThrow(/label/);
  });
});

describe("StatusBadge and PageHeader", () => {
  it("renders known and unknown statuses with words", async () => {
    const { container } = render(
      <div>
        <PageHeader title="Title" description="Desc" actions={<button type="button">Act</button>} />
        <StatusBadge status="approved" />
        <StatusBadge status="weird" />
      </div>,
    );
    expect(screen.getByRole("heading", { name: "Title" })).toBeInTheDocument();
    expect(screen.getByText("Approved")).toBeInTheDocument();
    expect(screen.getByText("weird")).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });
});
