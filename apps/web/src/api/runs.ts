/** Runs, regression runs and the live project event stream (docs/06-api.md "Runs" and §4). */
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { API_BASE, api } from "./client";
import { keys as projectKeys } from "./projects";
import type { PipelineOut, RunDetail, RunOut, RunPage, RunStarted } from "./types";

export const runKeys = {
  all: (pid: string) => ["runs", pid] as const,
  list: (pid: string) => ["runs", pid, "list"] as const,
  detail: (pid: string, rid: string) => ["runs", pid, "detail", rid] as const,
};

export function useRuns(pid: string) {
  return useQuery({
    queryKey: runKeys.list(pid),
    queryFn: () => api<RunPage>(`/projects/${pid}/runs`, { query: { limit: 50 } }),
  });
}

export function useRun(pid: string, rid: string) {
  return useQuery({
    queryKey: runKeys.detail(pid, rid),
    queryFn: () => api<RunDetail>(`/projects/${pid}/runs/${rid}`),
  });
}

export type StartRun = { env_id?: string | null; journeys: string[] };

/** Regression run of the approved cases (needs the pipeline `done`; 409 `STATE_CONFLICT` otherwise). */
export function useStartRun(pid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: StartRun) =>
      api<RunStarted>(`/projects/${pid}/runs`, {
        method: "POST",
        body: { env_id: body.env_id || null, journeys: body.journeys, source: "ui" },
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: projectKeys.pipeline(pid) });
      void qc.invalidateQueries({ queryKey: runKeys.all(pid) });
    },
  });
}

type PipelineEvent = { stage: string; status: string } | null;

function parse(data: unknown): unknown {
  try {
    return typeof data === "string" ? JSON.parse(data) : null;
  } catch {
    return undefined;
  }
}

/** Patch the stepper at once, then refetch for `entered_at` and history. */
export function applyPipelineEvent(qc: QueryClient, pid: string, ev: PipelineEvent): void {
  qc.setQueryData<PipelineOut>(projectKeys.pipeline(pid), (old) => {
    if (!old) return old;
    if (!ev) return { ...old, current: null };
    const current = old.current ? { ...old.current, ...ev } : { ...ev, entered_at: new Date().toISOString() };
    return { ...old, current } as PipelineOut;
  });
  void qc.invalidateQueries({ queryKey: projectKeys.pipeline(pid) });
  void qc.invalidateQueries({ queryKey: projectKeys.project(pid) });
}

/** Replace the run in the list (if loaded), then refetch the list and that run's detail. */
export function applyRunEvent(qc: QueryClient, pid: string, run: RunOut | null): void {
  if (!run) return;
  qc.setQueryData<RunPage>(runKeys.list(pid), (old) =>
    old && old.items.some((r) => r.id === run.id)
      ? { ...old, items: old.items.map((r) => (r.id === run.id ? run : r)) }
      : old,
  );
  void qc.invalidateQueries({ queryKey: runKeys.list(pid) });
  void qc.invalidateQueries({ queryKey: runKeys.detail(pid, run.id) });
}

export const RECONNECT_MS = 5_000;

/**
 * Subscribe to `GET /projects/{id}/events` (SSE). `pipeline` and `run` events patch the Query
 * cache. The browser reconnects by itself after a dropped stream (`retry: 3000`); if the stream
 * is closed for good (for example a 401), a new one is opened after RECONNECT_MS. Closed on
 * unmount. Returns whether the stream is open, so callers can stop polling.
 */
export function useProjectEvents(pid: string | undefined): boolean {
  const qc = useQueryClient();
  const [live, setLive] = useState(false);
  useEffect(() => {
    if (!pid || typeof EventSource === "undefined") return;
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;

    const open = () => {
      const es = new EventSource(`${API_BASE}/projects/${pid}/events`, { withCredentials: true });
      source = es;
      es.onopen = () => setLive(true);
      es.addEventListener("pipeline", (e) => {
        const data = parse((e as MessageEvent).data);
        if (data !== undefined) applyPipelineEvent(qc, pid, data as PipelineEvent);
      });
      es.addEventListener("run", (e) => {
        const data = parse((e as MessageEvent).data);
        if (data !== undefined) applyRunEvent(qc, pid, data as RunOut | null);
      });
      es.onerror = () => {
        setLive(false);
        if (es.readyState === EventSource.CLOSED && !stopped) {
          es.close();
          timer = setTimeout(open, RECONNECT_MS);
        }
      };
    };
    open();
    return () => {
      stopped = true;
      clearTimeout(timer);
      source?.close();
      setLive(false);
    };
  }, [pid, qc]);
  return live;
}
