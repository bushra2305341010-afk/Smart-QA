/**
 * Ingest → Understand → Plan → Design → Run → Report (docs/05 §4). Each step groups the
 * orchestrator's stages (apps/orchestrator/machine.py); a lock marks a human gate not yet passed.
 */
import type { StateOut } from "../api/types";

type Step = { label: string; stages: string[]; gate?: { stage: string; n: number } };

export const STEPS: Step[] = [
  { label: "Ingest", stages: ["ingest"] },
  { label: "Understand", stages: ["understand", "graph_review"], gate: { stage: "graph_review", n: 1 } },
  { label: "Plan", stages: ["plan", "plan_approval"], gate: { stage: "plan_approval", n: 2 } },
  { label: "Design", stages: ["design", "case_review"], gate: { stage: "case_review", n: 3 } },
  { label: "Run", stages: ["compile", "execute", "judge"] },
  { label: "Report", stages: ["bug_review", "report", "done"], gate: { stage: "bug_review", n: 4 } },
];

const STATUS_LABEL: Record<string, string> = {
  queued: "queued",
  running: "running",
  awaiting_approval: "awaiting approval",
  failed: "failed",
  cancelled: "cancelled",
  done: "done",
};

type Props = { current: StateOut | null | undefined };

export function StageStepper({ current }: Props) {
  const index = current ? STEPS.findIndex((s) => s.stages.includes(current.stage)) : -1;
  const finished = current?.stage === "done";
  return (
    <nav aria-label="Pipeline stages">
      <ol className="m-0 flex list-none flex-wrap items-center gap-1 p-0 text-xs">
        {STEPS.map((step, i) => {
          const isCurrent = i === index && !finished;
          const done = finished || i < index;
          const awaiting = isCurrent && current?.status === "awaiting_approval";
          const locked = Boolean(step.gate) && !done;
          const state = done ? "done" : isCurrent ? STATUS_LABEL[current!.status] ?? current!.status : "not started";
          return (
            <li
              key={step.label}
              aria-current={isCurrent ? "step" : undefined}
              className={`flex items-center gap-1 rounded-full border px-2 py-0.5 ${
                isCurrent
                  ? "border-primary font-semibold text-primary"
                  : done
                    ? "border-accent text-accent"
                    : "border-border text-muted"
              }`}
            >
              <span aria-hidden="true">{done ? "✓" : locked ? "🔒" : "○"}</span>
              <span>{step.label}</span>
              <span className="sr-only">
                {`: ${state}`}
                {locked && step.gate ? `, gate ${step.gate.n} not approved` : ""}
              </span>
              {awaiting ? <span aria-hidden="true">· review</span> : null}
            </li>
          );
        })}
      </ol>
      {!current ? <p className="m-0 mt-1 text-xs text-muted">Pipeline not started.</p> : null}
    </nav>
  );
}
