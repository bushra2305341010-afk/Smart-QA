import { useMemo, useState } from "react";
import { useApproveCases, useCases, useReviewCases } from "../../api/review";
import type { CaseOut } from "../../api/types";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { useHotkeys } from "../../hooks/useHotkeys";
import { useRequiredProjectId } from "../../hooks/useProjectId";
import { CaseDetail, isVerified } from "./CaseDetail";

/** Unverified cases first (they need a decision most), then by code. */
function ordered(cases: CaseOut[]): CaseOut[] {
  return [...cases].sort((a, b) => Number(isVerified(a)) - Number(isVerified(b)) || a.code.localeCompare(b.code));
}

/** Gate 3: approve cases whose expected result cites a verified quote. */
export function CaseReviewPage() {
  const pid = useRequiredProjectId();
  const cases = useCases(pid);
  let body;
  if (cases.isPending) body = <LoadingState label="Loading test cases…" />;
  else if (cases.error) body = <ErrorState error={cases.error} title="Could not load test cases" />;
  else if (cases.data.items.length === 0) {
    body = <EmptyState title="No test cases yet">Cases are designed after the coverage plan is approved (Gate 2).</EmptyState>;
  } else body = <CaseReview pid={pid} cases={ordered(cases.data.items)} more={cases.data.next_cursor !== null} />;
  return (
    <section>
      <PageHeader
        title="Case review"
        description="Gate 3 · Every expected result must cite its source. Keys: J/K move, A approve, R reject."
      />
      {body}
    </section>
  );
}

function CaseReview({ pid, cases, more }: { pid: string; cases: CaseOut[]; more: boolean }) {
  const review = useReviewCases(pid);
  const approveAll = useApproveCases(pid);
  const [index, setIndex] = useState(0);
  const current = cases[Math.min(index, cases.length - 1)]!;
  const counts = useMemo(() => {
    const pending = cases.filter((c) => c.review_status === "pending" || c.review_status === "edited").length;
    const uv = cases.filter((c) => !isVerified(c)).length;
    return { pending, uv };
  }, [cases]);

  const decide = (decision: "approved" | "rejected") => {
    if (decision === "approved" && !isVerified(current)) return;
    review.mutate(
      { case_ids: [current.id], decision },
      { onSuccess: () => setIndex((i) => Math.min(i + 1, cases.length - 1)) },
    );
  };
  useHotkeys({
    j: () => setIndex((i) => Math.min(i + 1, cases.length - 1)),
    k: () => setIndex((i) => Math.max(i - 1, 0)),
    a: () => decide("approved"),
    r: () => decide("rejected"),
  });

  return (
    <div className="flex flex-col gap-3">
      <div className="card flex flex-wrap items-center gap-4">
        <p className="m-0 text-sm" aria-live="polite">
          {counts.pending} pending · {counts.uv} Unable to Verify · {cases.length} cases{more ? " (first 200)" : ""}
        </p>
        <button
          type="button"
          className="btn-primary ml-auto"
          disabled={approveAll.isPending || counts.pending > 0}
          onClick={() => approveAll.mutate()}
        >
          Finish review (Gate 3)
        </button>
      </div>
      {approveAll.isSuccess ? (
        <p role="status" className="m-0 text-sm text-accent">
          Cases approved. They will be compiled and run next.
        </p>
      ) : null}
      {approveAll.error ? <ErrorState error={approveAll.error} title="Gate 3 not passed" /> : null}
      {review.error ? <ErrorState error={review.error} title="Decision not saved" /> : null}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <ul aria-label="Test cases" className="m-0 flex max-h-[70vh] list-none flex-col gap-1 overflow-auto p-0">
          {cases.map((c, i) => (
            <li key={c.id}>
              <button
                type="button"
                aria-current={c.id === current.id ? "true" : undefined}
                onClick={() => setIndex(i)}
                className={`flex w-full items-center justify-between gap-2 rounded border border-border bg-surface p-2 text-left text-sm ${
                  c.id === current.id ? "ring-2 ring-primary" : ""
                }`}
              >
                <span>
                  <span className="block font-mono text-xs text-muted">{c.code}</span>
                  {c.title}
                  {!isVerified(c) ? <span className="block text-xs font-semibold text-uv">? Unable to Verify</span> : null}
                </span>
                <StatusBadge status={c.review_status} />
              </button>
            </li>
          ))}
        </ul>
        <CaseDetail testCase={current} busy={review.isPending} onDecide={decide} />
      </div>
    </div>
  );
}
