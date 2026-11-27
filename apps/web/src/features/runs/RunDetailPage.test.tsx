import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RUN } from "../../test/fixtures";
import { FakeEventSource, SHA_SHOT, runDetail } from "../../test/runFixtures";
import { PID, errorBody, expectNoAxeViolations, mockApi, renderApp, shellRoutes, type Routes } from "../../test/utils";

const page = `/projects/${PID}/runs/${RUN}`;

function routes(over: Routes = {}): Routes {
  return { ...shellRoutes(), [`GET /projects/${PID}/runs/${RUN}`]: { body: runDetail }, ...over };
}

const caseRows = () => within(screen.getByRole("table", { name: "Cases in this run" })).getAllByRole("row").slice(1);

describe("RunDetailPage", () => {
  it("shows verdict tiles, progress and one row per case", async () => {
    mockApi(routes());
    const { container } = renderApp(page);
    const tiles = await screen.findByRole("list", { name: "Verdict totals" });
    expect(within(tiles).getByRole("button", { name: /1\s*Pass/ })).toBeInTheDocument();
    expect(within(tiles).getByRole("button", { name: /0\s*Flaky/ })).toBeInTheDocument();
    expect(screen.getByLabelText("Judged")).toHaveAttribute("value", "3");
    expect(screen.getByText("3 of 3")).toBeInTheDocument();
    expect(caseRows()).toHaveLength(3);
    const fail = caseRows()[1]!;
    expect(within(fail).getByText("TC-002")).toBeInTheDocument();
    expect(within(fail).getByRole("status", { name: "Verdict: Fail" })).toBeInTheDocument();
    expect(within(fail).getByText("J3.assertion")).toBeInTheDocument();
    expect(within(fail).getByText("2")).toBeInTheDocument();
    expect(within(caseRows()[2]!).getByText("Needs a human: Expected result has no verified quote")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "All runs" })).toHaveAttribute("href", `/projects/${PID}/runs`);
    await expectNoAxeViolations(container);
  });

  it("filters by tile, by the verdict select and by the Unable to Verify toggle", async () => {
    mockApi(routes());
    renderApp(page);
    const tiles = await screen.findByRole("list", { name: "Verdict totals" });
    const failTile = within(tiles).getByRole("button", { name: /Fail/ });
    await userEvent.click(failTile);
    expect(failTile).toHaveAttribute("aria-pressed", "true");
    expect(caseRows()).toHaveLength(1);
    await userEvent.click(failTile);
    expect(caseRows()).toHaveLength(3);

    await userEvent.selectOptions(screen.getByLabelText("Verdict"), "pass");
    expect(caseRows()).toHaveLength(1);
    expect(screen.getByText("1 of 3 cases")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Verdict"), "flaky");
    expect(screen.getByText("No cases match this filter")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Verdict"), "pending");
    expect(screen.getByText("No cases match this filter")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("checkbox", { name: /Only Unable to Verify/ }));
    expect(screen.getByLabelText("Verdict")).toBeDisabled();
    expect(caseRows()).toHaveLength(1);
    expect(within(caseRows()[0]!).getByText("TC-003")).toBeInTheDocument();
    await userEvent.click(within(tiles).getByRole("button", { name: /Pass/ }));
    expect(screen.getByRole("checkbox", { name: /Only Unable to Verify/ })).not.toBeChecked();
    expect(caseRows()).toHaveLength(1);
  });

  it("opens the evidence drawer with screenshots, downloads and plain-text failure", async () => {
    mockApi(routes());
    const { container } = renderApp(page);
    const opener = await screen.findByRole("button", { name: "Evidence for TC-002" });
    await userEvent.click(opener);
    const drawer = screen.getByRole("dialog", { name: /Quantity above 99 is rejected/ });
    const img = within(drawer).getByRole("img", { name: "Screenshot of TC-002 at step 3" });
    expect(img).toHaveAttribute("src", `/api/v1/projects/${PID}/evidence/${SHA_SHOT}`);
    expect(within(drawer).getByRole("link", { name: "Playwright trace" })).toHaveAttribute(
      "href",
      `/api/v1/projects/${PID}/evidence/${"b".repeat(64)}`,
    );
    expect(within(drawer).getByText("(end of test, 4.0 KB)")).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: "Compiled Playwright test (.py)" })).toHaveAttribute(
      "href",
      `/api/v1/projects/${PID}/cases/tc_2/compiled.py`,
    );
    expect(within(drawer).getByText("<b>Expected</b> error")).toBeInTheDocument();
    expect(drawer.querySelector("b")).toBeNull();
    expect(within(drawer).getByText("Maximum 99 items")).toBeInTheDocument();
    expect(within(drawer).getByText("Added 100 items")).toBeInTheDocument();
    expect(within(drawer).getByText("assertion · step 3")).toBeInTheDocument();
    expect(within(drawer).getByRole("button", { name: "Close evidence" })).toHaveFocus();
    await expectNoAxeViolations(container);

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it("shows the needs-a-human note for Unable to Verify and closes with the button", async () => {
    mockApi(routes());
    renderApp(page);
    await userEvent.click(await screen.findByRole("button", { name: "Evidence for TC-003" }));
    const drawer = screen.getByRole("dialog");
    expect(within(drawer).getByText(/Needs a human: this result could not be verified automatically/)).toBeInTheDocument();
    expect(within(drawer).getByText("No screenshots for this attempt.")).toBeInTheDocument();
    expect(within(drawer).getByText("1 attempt")).toBeInTheDocument();
    await userEvent.click(within(drawer).getByRole("button", { name: "Close evidence" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows rows without a verdict and live progress from the event stream", async () => {
    FakeEventSource.install();
    const running = {
      ...runDetail,
      status: "running",
      finished_at: null,
      totals: { cases: 4 },
      cases: [
        { ...runDetail.cases[0]!, verdict: null, confidence: null, level: null, rule: null, reason: null, status: "failed", blocked: "captcha" },
      ],
    };
    let calls = 0;
    mockApi(
      routes({
        [`GET /projects/${PID}/runs/${RUN}`]: () => ({ body: calls++ === 0 ? running : runDetail }),
      }),
    );
    const { container } = renderApp(page);
    expect(await screen.findByText("0 of 4")).toBeInTheDocument();
    const row = caseRows()[0]!;
    expect(within(row).getByText("failed")).toBeInTheDocument();
    expect(within(row).getByText("captcha")).toBeInTheDocument();
    await userEvent.click(within(row).getByRole("button", { name: "Evidence for TC-001" }));
    const drawer = screen.getByRole("dialog");
    expect(within(drawer).getByText("No verdict yet")).toBeInTheDocument();
    expect(within(drawer).getByText("captcha")).toBeInTheDocument();
    await expectNoAxeViolations(container);
    await userEvent.click(within(drawer).getByRole("button", { name: "Close evidence" }));

    FakeEventSource.last.emit("run", { ...runDetail, cases: undefined });
    expect(await screen.findByText("3 of 3")).toBeInTheDocument();
  });

  it("shows an empty run and a load error", async () => {
    mockApi(routes({ [`GET /projects/${PID}/runs/${RUN}`]: { body: { ...runDetail, totals: {}, cases: [] } } }));
    const { container, unmount } = renderApp(page);
    expect(await screen.findByText("No results yet")).toBeInTheDocument();
    expect(screen.getByText("0 of 0")).toBeInTheDocument();
    await expectNoAxeViolations(container);
    unmount();

    mockApi(routes({ [`GET /projects/${PID}/runs/${RUN}`]: { status: 404, body: errorBody("NOT_FOUND", "Run not found") } }));
    renderApp(page);
    expect(await screen.findByText("Could not load the run")).toBeInTheDocument();
  });
});
