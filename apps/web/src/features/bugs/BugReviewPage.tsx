import { useState } from "react";
import { useApproveBugs, useBugs } from "../../api/review";
import type { BugOut } from "../../api/types";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { useRequiredProjectId } from "../../hooks/useProjectId";
import { BugDetail } from "./BugDetail";

const SEVERITY_CLASS: Record<string, string> = {
  critical: "text-sev-critical",
  high: "text-sev-high",
  medium: "text-sev-medium",
  low: "text-sev-low",
};

/** Gate 4: nothing is filed until every draft is decided and the lead presses "Confirm & file". */
export function BugReviewPage() {
  const pid = useRequiredProjectId();
  const bugs = useBugs(pid);
  let body;
  if (bugs.isPending) body = <LoadingState label="Loading bug drafts…" />;
  else if (bugs.error) body = <ErrorState error={bugs.error} title="Could not load bugs" />;
  else if (bugs.data.length === 0) {
    body = <EmptyState title="No bug drafts">The judge drafts bugs only for confirmed failures.</EmptyState>;
  } else body = <BugReview pid={pid} bugs={bugs.data} />;
  return (
    <section>
      <PageHeader title="Bug review" description="Gate 4 · Confirm or dismiss each draft, then file." />
      {body}
    </section>
  );
}

function BugReview({ pid, bugs }: { pid: string; bugs: BugOut[] }) {
  const file = useApproveBugs(pid);
  const sorted = [...bugs].sort((a, b) => Number(b.status === "draft") - Number(a.status === "draft"));
  const [selected, setSelected] = useState(sorted[0]!.id);
  const current = sorted.find((b) => b.id === selected) ?? sorted[0]!;
  const drafts = bugs.filter((b) => b.status === "draft").length;
  const confirmed = bugs.filter((b) => b.status === "confirmed").length;

  return (
    <div className="flex flex-col gap-3">
      <div className="card flex flex-wrap items-center gap-4">
        <p className="m-0 text-sm" aria-live="polite">
          {drafts} drafts to decide · {confirmed} confirmed
        </p>
        <button
          type="button"
          className="btn-primary ml-auto"
          disabled={file.isPending || drafts > 0}
          aria-describedby="file-note"
          onClick={() => file.mutate()}
        >
          Confirm &amp; file
        </button>
        <p id="file-note" className="m-0 w-full text-xs text-muted">
          {drafts > 0 ? "Decide every draft first." : "Confirmed bugs are filed to the tracker by the report stage."}
        </p>
      </div>
      {file.isSuccess ? (
        <p role="status" className="m-0 text-sm text-accent">
          Gate 4 approved. Confirmed bugs will be filed with their evidence.
        </p>
      ) : null}
      {file.error ? <ErrorState error={file.error} title="Bugs not filed" /> : null}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <ul aria-label="Bugs" className="m-0 flex list-none flex-col gap-1 p-0">
          {sorted.map((b) => (
            <li key={b.id}>
              <button
                type="button"
                aria-current={b.id === current.id ? "true" : undefined}
                onClick={() => setSelected(b.id)}
                className={`flex w-full items-center justify-between gap-2 rounded border border-border bg-surface p-2 text-left text-sm ${
                  b.id === current.id ? "ring-2 ring-primary" : ""
                }`}
              >
                <span>
                  <span className={`block text-xs font-semibold ${SEVERITY_CLASS[b.severity] ?? "text-muted"}`}>
                    {b.severity}
                  </span>
                  {b.title}
                </span>
                <StatusBadge status={b.status} />
              </button>
            </li>
          ))}
        </ul>
        <BugDetail pid={pid} bug={current} />
      </div>
    </div>
  );
}
