/** Names for the generated OpenAPI shapes (`pnpm gen:api` rewrites schema.d.ts). */
import type { components } from "./schema";

type S = components["schemas"];

export type UserOut = S["UserOut"];
export type SessionOut = S["SessionOut"];
export type MfaRequiredOut = S["MfaRequiredOut"];
export type MeOut = S["MeOut"];
export type TotpSetupOut = S["TotpSetupOut"];
export type ProjectOut = S["ProjectOut"];
export type SourceOut = S["SourceOut"];
export type SourcePage = S["Page_SourceOut_"];
export type EnvironmentOut = S["EnvironmentOut"];
export type EnvironmentIn = S["EnvironmentIn"];
export type PipelineOut = S["PipelineOut"];
export type StateOut = S["StateOut"];
export type CostsOut = S["CostsOut"];
export type VersionOut = S["VersionOut"];
export type GraphOut = S["GraphOut"];
export type NodeOut = S["NodeOut"];
export type CitationOut = S["CitationOut"];
export type PlanOut = S["PlanOut"];
export type SegmentOut = S["SegmentOut"];
export type CaseOut = S["CaseOut"];
export type CasePage = S["CasePage"];
export type BugOut = S["BugOut"];
export type BugEditIn = S["BugEditIn"];
export type DuplicateOut = S["DuplicateOut"];
export type RunOut = S["RunOut"];
export type RunPage = S["Page_RunOut_"];
export type RunDetail = S["RunDetail"];
export type RunIn = S["RunIn"];
export type RunStarted = S["RunStarted"];
export type CaseRow = S["CaseRow"];
export type EvidenceOut = S["EvidenceOut"];

/** `RunOut.totals`: compiler counts, plus `verdicts` once the Judge has run (apps/workers/judge.py). */
export type RunTotals = {
  cases?: number;
  compiled?: number;
  partial?: number;
  not_compiled?: number;
  verdicts?: Partial<Record<string, number>>;
};

/** `CaseRow.failure` (packages/contracts/run.py Failure). */
export type RunFailure = {
  kind?: string;
  message?: string;
  step_n?: number | null;
  expected?: string | null;
  actual?: string | null;
};

/** A plan segment's "why this many" row (packages/contracts/plan.py TechniqueRow). */
export type TechniqueRow = { technique: string; count: number; reason: string };

/** `PlanOut.cost_estimate`: CostEstimate when prices are set, else the reason it is missing. */
export type CostEstimate =
  | { available: true; model: string; input_tokens: number; output_tokens: number; usd: number; minutes: number }
  | { available: false; reason: string };

/** `CaseOut.citation` as written by the designer (apps/workers/designer.py). */
export type CaseCitation = {
  status: "verified" | "unable_to_verify" | string;
  quote?: string;
  source_id?: string;
  start_offset?: number;
  end_offset?: number;
  reason?: string;
};
