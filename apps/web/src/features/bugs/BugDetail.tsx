import { useEffect, useState, type FormEvent } from "react";
import { useBugDecision, useDuplicates, useEditBug } from "../../api/review";
import type { BugEditIn, BugOut } from "../../api/types";
import { StatusBadge } from "../../components/StatusBadge";
import { ErrorState, LoadingState } from "../../components/States";

type Severity = NonNullable<BugEditIn["severity"]>;
const SEVERITIES: Severity[] = ["critical", "high", "medium", "low"];

function Duplicates({ pid, bugId }: { pid: string; bugId: string }) {
  const dups = useDuplicates(pid, bugId);
  if (dups.isPending) return <LoadingState label="Checking for duplicates…" />;
  if (dups.error) return <ErrorState error={dups.error} title="Duplicate check failed" />;
  if (dups.data.length === 0) return <p className="m-0 text-sm text-muted">No similar issues found.</p>;
  return (
    <div role="alert" className="rounded border border-flaky bg-flaky-bg p-2 text-sm text-text">
      <p className="m-0 font-semibold">Possible duplicates</p>
      <ul className="m-0 pl-5">
        {dups.data.map((d) => (
          <li key={`${d.source}:${d.ref}`}>
            {d.title} <span className="text-muted">({d.source === "tracker" ? "tracker" : "this project"} · {d.ref})</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** One bug draft: edit, check duplicates, confirm or dismiss with a reason. Body is plain text. */
export function BugDetail({ pid, bug }: { pid: string; bug: BugOut }) {
  const decision = useBugDecision(pid);
  const edit = useEditBug(pid);
  const isDraft = bug.status === "draft";
  const [title, setTitle] = useState(bug.title);
  const [severity, setSeverity] = useState(bug.severity);
  const [body, setBody] = useState(bug.body_md);
  const [reason, setReason] = useState("");
  useEffect(() => {
    setTitle(bug.title);
    setSeverity(bug.severity);
    setBody(bug.body_md);
    setReason("");
  }, [bug.id, bug.title, bug.severity, bug.body_md]);
  const dirty = title !== bug.title || severity !== bug.severity || body !== bug.body_md;

  const save = (e: FormEvent) => {
    e.preventDefault();
    edit.mutate({ bugId: bug.id, edit: { title, severity: severity as Severity, body_md: body } });
  };
  const dismiss = (e: FormEvent) => {
    e.preventDefault();
    decision.mutate({ bugId: bug.id, action: "dismiss", reason: reason.trim() });
  };

  return (
    <article aria-labelledby="bug-title" className="card flex flex-col gap-3">
      <header>
        <p className="m-0 font-mono text-xs text-muted">
          {bug.id} · run {bug.run_id} · case {bug.case_id}
        </p>
        <h2 id="bug-title" className="m-0 text-lg font-semibold">
          {bug.title}
        </h2>
        <StatusBadge status={bug.status} />
        {bug.tracker_ref ? <p className="m-0 text-sm">Tracker: {bug.tracker_ref}</p> : null}
      </header>
      <Duplicates pid={pid} bugId={bug.id} />
      {isDraft ? (
        <form onSubmit={save} className="flex flex-col gap-2">
          <div>
            <label className="label" htmlFor="bug-edit-title">
              Title
            </label>
            <input id="bug-edit-title" className="field" required value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="bug-edit-severity">
              Severity
            </label>
            <select id="bug-edit-severity" className="field w-40" value={severity} onChange={(e) => setSeverity(e.target.value)}>
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="bug-edit-body">
              Report (Markdown, shown as plain text)
            </label>
            <textarea id="bug-edit-body" className="field min-h-48 font-mono" value={body} onChange={(e) => setBody(e.target.value)} />
          </div>
          <button type="submit" className="btn-secondary self-start" disabled={!dirty || edit.isPending}>
            Save draft
          </button>
          {edit.error ? <ErrorState error={edit.error} title="Draft not saved" /> : null}
        </form>
      ) : (
        <pre className="m-0 whitespace-pre-wrap rounded bg-surface-2 p-2 font-mono text-sm">{bug.body_md}</pre>
      )}
      {isDraft ? (
        <div className="flex flex-col gap-2 border-t border-border pt-3">
          <button
            type="button"
            className="btn-primary self-start"
            disabled={decision.isPending || dirty}
            onClick={() => decision.mutate({ bugId: bug.id, action: "confirm" })}
          >
            Confirm bug
          </button>
          {dirty ? <p className="m-0 text-xs text-muted">Save your edits before confirming.</p> : null}
          <form onSubmit={dismiss} className="flex flex-wrap items-end gap-2">
            <div className="min-w-64 flex-1">
              <label className="label" htmlFor="bug-dismiss-reason">
                Dismiss reason (teaches the judge)
              </label>
              <input
                id="bug-dismiss-reason"
                className="field"
                required
                maxLength={500}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </div>
            <button type="submit" className="btn-danger" disabled={decision.isPending || !reason.trim()}>
              Dismiss
            </button>
          </form>
          {decision.error ? <ErrorState error={decision.error} title="Decision not saved" /> : null}
        </div>
      ) : null}
    </article>
  );
}
