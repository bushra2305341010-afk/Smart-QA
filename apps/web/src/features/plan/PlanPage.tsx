import { usePipelineEvent } from "../../api/projects";
import { useApprovePlan, useEditSegment, usePlans } from "../../api/review";
import type { CostEstimate, PlanOut } from "../../api/types";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { useRequiredProjectId } from "../../hooks/useProjectId";
import { SegmentRow } from "./SegmentRow";

/** Gate 2: suggested counts with reasons, human-approved counts, cost before generation. */
export function PlanPage() {
  const pid = useRequiredProjectId();
  const plans = usePlans(pid);
  let body;
  if (plans.isPending) body = <LoadingState label="Loading the coverage plan…" />;
  else if (plans.error) body = <ErrorState error={plans.error} title="Could not load plans" />;
  else if (!plans.data[0]) {
    body = <EmptyState title="No plan yet">The planner runs after the graph is approved (Gate 1).</EmptyState>;
  } else body = <PlanReview pid={pid} plan={plans.data[0]} />;
  return (
    <section>
      <PageHeader title="Coverage plan" description="Gate 2 · How many cases per journey, and why." />
      {body}
    </section>
  );
}

function CostSummary({ plan }: { plan: PlanOut }) {
  const est = plan.cost_estimate as CostEstimate;
  if (!est.available) {
    return <p className="m-0 text-sm text-muted">Cost estimate unavailable: {est.reason}</p>;
  }
  // The stored estimate is for the suggested total; scale it for edited counts until approval
  // recomputes it on the server.
  const scale = plan.suggested_total > 0 ? plan.approved_total / plan.suggested_total : 1;
  const usd = est.usd * scale;
  const minutes = est.minutes * scale;
  return (
    <p className="m-0 text-sm" aria-live="polite">
      Estimated design cost <span className="font-semibold">≈ ${usd.toFixed(2)}</span> · about{" "}
      {Math.ceil(minutes)} min · model {est.model}
    </p>
  );
}

function PlanReview({ pid, plan }: { pid: string; plan: PlanOut }) {
  const edit = useEditSegment(pid, plan.id);
  const approve = useApprovePlan(pid, plan.id);
  const replan = usePipelineEvent(pid);
  const editable = plan.status === "draft";
  return (
    <div className="flex flex-col gap-3">
      <div className="card flex flex-wrap items-center gap-4">
        <StatusBadge status={plan.status} />
        <p className="m-0 text-sm">
          Suggested <span className="font-semibold">{plan.suggested_total}</span> · Approved{" "}
          <span className="font-semibold">{plan.approved_total}</span> cases
        </p>
        <CostSummary plan={plan} />
        {editable ? (
          <div className="ml-auto flex gap-2">
            <button type="button" className="btn-secondary" disabled={replan.isPending} onClick={() => replan.mutate("plan_edited")}>
              Re-plan
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={approve.isPending || plan.approved_total < 1}
              onClick={() => approve.mutate()}
            >
              Approve plan
            </button>
          </div>
        ) : null}
      </div>
      {approve.isSuccess ? (
        <p role="status" className="m-0 text-sm text-accent">
          Plan approved. Test design starts next.
        </p>
      ) : null}
      {approve.error ? <ErrorState error={approve.error} title="Plan not approved" /> : null}
      {edit.error ? <ErrorState error={edit.error} title="Count not saved" /> : null}
      {replan.error ? <ErrorState error={replan.error} title="Could not re-plan" /> : null}
      {plan.segments.length === 0 ? (
        <EmptyState title="This plan has no journeys" />
      ) : (
        <table className="w-full border-collapse rounded-card bg-surface text-sm">
          <caption className="sr-only">Plan segments, riskiest first</caption>
          <thead>
            <tr className="border-b border-border text-left text-muted">
              <th scope="col" className="p-2">Journey</th>
              <th scope="col" className="p-2">Techniques and reasons</th>
              <th scope="col" className="p-2 text-right">Suggested</th>
              <th scope="col" className="p-2">Approved</th>
            </tr>
          </thead>
          <tbody>
            {plan.segments.map((seg) => (
              <SegmentRow
                key={seg.id}
                segment={seg}
                editable={editable}
                busy={edit.isPending}
                onSave={(count) => edit.mutate({ segmentId: seg.id, count })}
              />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
