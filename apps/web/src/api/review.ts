/** Query hooks for the four human gates (graph, plan, cases, bugs). */
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api } from "./client";
import { keys as projectKeys } from "./projects";
import type {
  BugEditIn,
  BugOut,
  CasePage,
  CaseOut,
  DuplicateOut,
  GraphOut,
  NodeOut,
  PlanOut,
  SegmentOut,
  VersionOut,
} from "./types";

export const reviewKeys = {
  graphVersions: (pid: string) => ["graph", pid] as const,
  graph: (pid: string, gv: string) => ["graph", pid, gv] as const,
  plans: (pid: string) => ["plans", pid] as const,
  cases: (pid: string) => ["cases", pid] as const,
  bugs: (pid: string) => ["bugs", pid] as const,
  duplicates: (pid: string, bug: string) => ["bugs", pid, bug, "duplicates"] as const,
};

function refreshPipeline(qc: QueryClient, pid: string) {
  void qc.invalidateQueries({ queryKey: projectKeys.pipeline(pid) });
  void qc.invalidateQueries({ queryKey: projectKeys.project(pid) });
}

// ---- Gate 1: graph ----

export function useGraphVersions(pid: string) {
  return useQuery({
    queryKey: reviewKeys.graphVersions(pid),
    queryFn: () => api<VersionOut[]>(`/projects/${pid}/graph`),
  });
}

export function useGraph(pid: string, gv: string | undefined) {
  return useQuery({
    queryKey: reviewKeys.graph(pid, gv ?? ""),
    queryFn: () => api<GraphOut>(`/projects/${pid}/graph/${gv}`),
    enabled: Boolean(gv),
  });
}

export type NodeReview = { review_status: "approved" | "rejected" | "edited"; label?: string };

export function useReviewNode(pid: string, gv: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ nodeId, review }: { nodeId: string; review: NodeReview }) =>
      api<NodeOut>(`/projects/${pid}/graph/${gv}/nodes/${nodeId}`, { method: "PATCH", body: review }),
    onSuccess: () => qc.invalidateQueries({ queryKey: reviewKeys.graphVersions(pid) }),
  });
}

export function useApproveGraph(pid: string, gv: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<VersionOut>(`/projects/${pid}/graph/${gv}/approve`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: reviewKeys.graphVersions(pid) });
      refreshPipeline(qc, pid);
    },
  });
}

// ---- Gate 2: plan ----

export function usePlans(pid: string) {
  return useQuery({ queryKey: reviewKeys.plans(pid), queryFn: () => api<PlanOut[]>(`/projects/${pid}/plans`) });
}

export function useEditSegment(pid: string, plan: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ segmentId, count }: { segmentId: string; count: number }) =>
      api<SegmentOut>(`/projects/${pid}/plans/${plan}/segments/${segmentId}`, {
        method: "PATCH",
        body: { approved_count: count },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: reviewKeys.plans(pid) }),
  });
}

export function useApprovePlan(pid: string, plan: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<PlanOut>(`/projects/${pid}/plans/${plan}/approve`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: reviewKeys.plans(pid) });
      refreshPipeline(qc, pid);
    },
  });
}

// ---- Gate 3: cases ----

export function useCases(pid: string) {
  return useQuery({
    queryKey: reviewKeys.cases(pid),
    queryFn: () => api<CasePage>(`/projects/${pid}/cases`, { query: { limit: 200 } }),
  });
}

export function useReviewCases(pid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { case_ids: string[]; decision: "approved" | "rejected" }) =>
      api<{ updated: number }>(`/projects/${pid}/cases/review`, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: reviewKeys.cases(pid) }),
  });
}

export function useApproveCases(pid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<Record<string, unknown>>(`/projects/${pid}/cases/approve`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: reviewKeys.cases(pid) });
      refreshPipeline(qc, pid);
    },
  });
}

export type { CaseOut };

// ---- Gate 4: bugs ----

export function useBugs(pid: string) {
  return useQuery({ queryKey: reviewKeys.bugs(pid), queryFn: () => api<BugOut[]>(`/projects/${pid}/bugs`) });
}

export function useDuplicates(pid: string, bugId: string) {
  return useQuery({
    queryKey: reviewKeys.duplicates(pid, bugId),
    queryFn: () => api<DuplicateOut[]>(`/projects/${pid}/bugs/${bugId}/duplicates`),
    retry: false,
  });
}

export function useBugDecision(pid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (d: { bugId: string; action: "confirm" } | { bugId: string; action: "dismiss"; reason: string }) =>
      api<BugOut>(`/projects/${pid}/bugs/${d.bugId}/${d.action}`, {
        method: "POST",
        body: d.action === "dismiss" ? { reason: d.reason } : undefined,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: reviewKeys.bugs(pid) }),
  });
}

export function useEditBug(pid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ bugId, edit }: { bugId: string; edit: BugEditIn }) =>
      api<BugOut>(`/projects/${pid}/bugs/${bugId}`, { method: "PATCH", body: edit }),
    onSuccess: () => qc.invalidateQueries({ queryKey: reviewKeys.bugs(pid) }),
  });
}

export function useApproveBugs(pid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<Record<string, string>>(`/projects/${pid}/bugs/approve`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: reviewKeys.bugs(pid) });
      refreshPipeline(qc, pid);
    },
  });
}
