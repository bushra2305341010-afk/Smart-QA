import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { RUN } from "../test/fixtures";
import { FakeEventSource, runSummary } from "../test/runFixtures";
import { PID } from "../test/utils";
import { keys } from "./projects";
import { RECONNECT_MS, applyRunEvent, runKeys, useProjectEvents } from "./runs";
import type { PipelineOut, RunPage } from "./types";

function setup(pid: string | undefined) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const pipeline: PipelineOut = {
    current: { stage: "execute", status: "running", entered_at: "2026-11-26T10:00:00Z" },
    history: [],
  };
  qc.setQueryData(keys.pipeline(PID), pipeline);
  qc.setQueryData<RunPage>(runKeys.list(PID), { items: [{ ...runSummary, status: "running" }], next_cursor: null });
  const invalidate = vi.spyOn(qc, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  const hook = renderHook(() => useProjectEvents(pid), { wrapper });
  return { qc, invalidate, hook };
}

const invalidated = (spy: { mock: { calls: unknown[][] } }) =>
  spy.mock.calls.map((c) => JSON.stringify((c[0] as { queryKey: unknown }).queryKey));

describe("useProjectEvents", () => {
  beforeEach(() => FakeEventSource.install());

  it("opens the project stream with credentials and reports when it is live", () => {
    const { hook } = setup(PID);
    const es = FakeEventSource.last;
    expect(es.url).toBe(`/api/v1/projects/${PID}/events`);
    expect(es.withCredentials).toBe(true);
    expect(hook.result.current).toBe(false);
    act(() => es.open());
    expect(hook.result.current).toBe(true);
  });

  it("patches the stepper and invalidates the pipeline on a pipeline event", () => {
    const { qc, invalidate } = setup(PID);
    act(() => FakeEventSource.last.emit("pipeline", { stage: "judge", status: "queued" }));
    const data = qc.getQueryData<PipelineOut>(keys.pipeline(PID));
    expect(data?.current).toMatchObject({ stage: "judge", status: "queued", entered_at: "2026-11-26T10:00:00Z" });
    expect(invalidated(invalidate)).toEqual(
      expect.arrayContaining([JSON.stringify(keys.pipeline(PID)), JSON.stringify(keys.project(PID))]),
    );
  });

  it("clears the stepper when the pipeline is gone and fills it when there was none", () => {
    const { qc } = setup(PID);
    act(() => FakeEventSource.last.emit("pipeline", null));
    expect(qc.getQueryData<PipelineOut>(keys.pipeline(PID))?.current).toBeNull();
    act(() => FakeEventSource.last.emit("pipeline", { stage: "ingest", status: "running" }));
    expect(qc.getQueryData<PipelineOut>(keys.pipeline(PID))?.current).toMatchObject({ stage: "ingest", status: "running" });
  });

  it("patches the run in the list and invalidates the run queries on a run event", () => {
    const { qc, invalidate } = setup(PID);
    act(() => FakeEventSource.last.emit("run", runSummary));
    expect(qc.getQueryData<RunPage>(runKeys.list(PID))?.items[0]?.status).toBe("completed");
    expect(invalidated(invalidate)).toEqual(
      expect.arrayContaining([JSON.stringify(runKeys.list(PID)), JSON.stringify(runKeys.detail(PID, RUN))]),
    );
  });

  it("ignores malformed data and empty run events", () => {
    const { invalidate } = setup(PID);
    act(() => FakeEventSource.last.emit("pipeline", "{not json"));
    act(() => FakeEventSource.last.emit("run", null));
    expect(invalidate).not.toHaveBeenCalled();
  });

  it("reconnects after the stream is closed for good, and stops on unmount", () => {
    vi.useFakeTimers();
    try {
      const { hook } = setup(PID);
      const first = FakeEventSource.last;
      act(() => first.open());
      act(() => first.fail(false)); // the browser retries by itself
      expect(hook.result.current).toBe(false);
      act(() => vi.advanceTimersByTime(RECONNECT_MS));
      expect(FakeEventSource.instances).toHaveLength(1);
      act(() => first.fail(true));
      act(() => vi.advanceTimersByTime(RECONNECT_MS));
      expect(FakeEventSource.instances).toHaveLength(2);
      const second = FakeEventSource.last;
      hook.unmount();
      expect(second.readyState).toBe(FakeEventSource.CLOSED);
      second.fail(true);
      vi.advanceTimersByTime(RECONNECT_MS * 2);
      expect(FakeEventSource.instances).toHaveLength(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it("does nothing without a project or without EventSource", () => {
    setup(undefined);
    expect(FakeEventSource.instances).toHaveLength(0);
    vi.stubGlobal("EventSource", undefined);
    const { hook } = setup(PID);
    expect(hook.result.current).toBe(false);
  });
});

describe("applyRunEvent", () => {
  it("leaves an unloaded list alone but still invalidates", () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, "invalidateQueries");
    applyRunEvent(qc, PID, runSummary);
    expect(qc.getQueryData(runKeys.list(PID))).toBeUndefined();
    expect(invalidate).toHaveBeenCalledTimes(2);
  });
});
