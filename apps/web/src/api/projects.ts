import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  CostsOut,
  EnvironmentIn,
  EnvironmentOut,
  PipelineOut,
  ProjectOut,
  SourceOut,
  SourcePage,
  StateOut,
} from "./types";

export const keys = {
  projects: ["projects"] as const,
  project: (pid: string) => ["projects", pid] as const,
  sources: (pid: string) => ["sources", pid] as const,
  environments: (pid: string) => ["environments", pid] as const,
  pipeline: (pid: string) => ["pipeline", pid] as const,
  costs: (pid: string) => ["costs", pid] as const,
};

export function useProjects() {
  return useQuery({ queryKey: keys.projects, queryFn: () => api<ProjectOut[]>("/projects") });
}

export function useProject(pid: string) {
  return useQuery({ queryKey: keys.project(pid), queryFn: () => api<ProjectOut>(`/projects/${pid}`) });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api<ProjectOut>("/projects", { method: "POST", body: { name } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.projects });
      void qc.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

export function useSources(pid: string) {
  return useQuery({
    queryKey: keys.sources(pid),
    queryFn: () => api<SourcePage>(`/projects/${pid}/sources`, { query: { limit: 200 } }),
  });
}

export function useUploadSource(pid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api<SourceOut>(`/projects/${pid}/sources/upload`, { method: "POST", body: form });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.sources(pid) }),
  });
}

export function useImportRepo(pid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { url: string; ref?: string | null }) =>
      api<SourceOut>(`/projects/${pid}/sources/repo`, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.sources(pid) }),
  });
}

export function useEnvironments(pid: string) {
  return useQuery({
    queryKey: keys.environments(pid),
    queryFn: () => api<EnvironmentOut[]>(`/projects/${pid}/environments`),
  });
}

export function useCreateEnvironment(pid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: EnvironmentIn) =>
      api<EnvironmentOut>(`/projects/${pid}/environments`, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.environments(pid) }),
  });
}

export function usePipeline(pid: string) {
  return useQuery({
    queryKey: keys.pipeline(pid),
    queryFn: () => api<PipelineOut>(`/projects/${pid}/pipeline`),
    // Until the SSE hook lands (run dashboard), poll so the stepper follows workers.
    refetchInterval: 10_000,
  });
}

/** Send a human pipeline event (`start`, `retry`, `cancel`, `graph_rejected`, `plan_edited`, ...). */
export function usePipelineEvent(pid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (event: string) =>
      api<StateOut>(`/projects/${pid}/pipeline/events`, { method: "POST", body: { event } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.pipeline(pid) });
      void qc.invalidateQueries({ queryKey: keys.project(pid) });
    },
  });
}

export function useCosts(pid: string) {
  return useQuery({ queryKey: keys.costs(pid), queryFn: () => api<CostsOut>(`/projects/${pid}/costs`) });
}
