/** Run dashboard data (GET /runs, GET /runs/{run}) for tests. */
import { vi } from "vitest";
import type { CaseRow, RunDetail, RunOut } from "../api/types";
import { RUN } from "./fixtures";

export const ENV = "env_" + "4".repeat(32);
export const SHA_SHOT = "a".repeat(64);
export const SHA_TRACE = "b".repeat(64);

export const runSummary: RunOut = {
  id: RUN,
  status: "completed",
  env_id: ENV,
  env_name: "Staging",
  started_at: "2026-11-26T10:00:00Z",
  finished_at: "2026-11-26T10:05:00Z",
  totals: { cases: 3, compiled: 3, partial: 0, not_compiled: 0, verdicts: { pass: 1, fail: 1, unable_to_verify: 1 } },
  created_at: "2026-11-26T09:59:00Z",
};

export const caseRow = (over: Partial<CaseRow> = {}): CaseRow => ({
  case_id: "tc_1",
  code: "TC-001",
  title: "Checkout with one item",
  attempts: 1,
  status: "passed",
  verdict: "pass",
  confidence: 0.95,
  level: "high",
  rule: "J1.pass",
  reason: "All expectations held",
  failure: null,
  blocked: null,
  result_id: "res_1",
  evidence: [],
  ...over,
});

export const failedRow = caseRow({
  case_id: "tc_2",
  code: "TC-002",
  title: "Quantity above 99 is rejected",
  attempts: 2,
  status: "failed",
  verdict: "fail",
  confidence: 0.9,
  level: "high",
  rule: "J3.assertion",
  reason: "Failed the same way twice",
  failure: { kind: "assertion", message: "<b>Expected</b> error", step_n: 3, expected: "Maximum 99 items", actual: "Added 100 items" },
  result_id: "res_2",
  evidence: [
    { kind: "screenshot", step_n: 3, sha256: SHA_SHOT, size: 2048 },
    { kind: "trace", step_n: null, sha256: SHA_TRACE, size: 4096 },
  ],
});

export const uvRow = caseRow({
  case_id: "tc_3",
  code: "TC-003",
  title: "Coupon applies",
  verdict: "unable_to_verify",
  confidence: 0.3,
  level: "low",
  rule: "J0.uncited",
  reason: "Expected result has no verified quote",
  result_id: "res_3",
});

export const runDetail: RunDetail = { ...runSummary, cases: [caseRow(), failedRow, uvRow] };

/** A controllable stand-in for the browser's EventSource (jsdom has none). */
export class FakeEventSource {
  static instances: FakeEventSource[] = [];
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  readonly url: string;
  readonly withCredentials: boolean;
  readyState = FakeEventSource.CONNECTING;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private listeners = new Map<string, ((e: MessageEvent) => void)[]>();

  constructor(url: string, init?: { withCredentials?: boolean }) {
    this.url = url;
    this.withCredentials = Boolean(init?.withCredentials);
    FakeEventSource.instances.push(this);
  }

  addEventListener(name: string, fn: (e: MessageEvent) => void) {
    this.listeners.set(name, [...(this.listeners.get(name) ?? []), fn]);
  }

  close() {
    this.readyState = FakeEventSource.CLOSED;
  }

  open() {
    this.readyState = FakeEventSource.OPEN;
    this.onopen?.();
  }

  emit(name: string, data: unknown) {
    const raw = typeof data === "string" ? data : JSON.stringify(data);
    for (const fn of this.listeners.get(name) ?? []) fn(new MessageEvent(name, { data: raw }));
  }

  fail(closed: boolean) {
    if (closed) this.readyState = FakeEventSource.CLOSED;
    this.onerror?.();
  }

  static install() {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  }

  static get last(): FakeEventSource {
    const es = FakeEventSource.instances.at(-1);
    if (!es) throw new Error("No EventSource opened");
    return es;
  }
}
