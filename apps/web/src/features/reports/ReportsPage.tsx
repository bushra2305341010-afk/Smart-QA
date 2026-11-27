import { useState } from "react";
import { Link } from "react-router-dom";
import { downloadUrl } from "../../api/client";
import { useRuns } from "../../api/runs";
import { PageHeader } from "../../components/PageHeader";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { useRequiredProjectId } from "../../hooks/useProjectId";

const RUN_ID = /^run_[0-9a-f]{32}$/;

function Downloads({ pid, runId }: { pid: string; runId: string }) {
  return (
    <li className="flex flex-wrap items-center gap-2 rounded border border-border p-2 text-sm">
      <Link to={`/projects/${pid}/runs/${runId}`} className="font-mono text-primary underline">
        {runId}
      </Link>
      <a className="btn-secondary ml-auto" href={downloadUrl(`/projects/${pid}/runs/${runId}/export.xlsx`)} download>
        Excel workbook<span className="sr-only"> for {runId}</span>
      </a>
      <a className="btn-secondary" href={downloadUrl(`/projects/${pid}/runs/${runId}/evidence-pack`)} download>
        Evidence pack<span className="sr-only"> for {runId}</span>
      </a>
    </li>
  );
}

/** Six-sheet Excel workbook and HTML evidence pack per run (from GET /runs, plus any run ID typed in). */
export function ReportsPage() {
  const pid = useRequiredProjectId();
  const list = useRuns(pid);
  const [typed, setTyped] = useState("");
  const [extra, setExtra] = useState<string[]>([]);
  const listed = (list.data?.items ?? []).map((r) => r.id);
  const runs = [...new Set([...listed, ...extra])];
  const valid = RUN_ID.test(typed.trim());

  return (
    <section>
      <PageHeader
        title="Reports"
        description="Open artifacts: Excel workbook and evidence pack per run."
        actions={
          <Link to={`/projects/${pid}/runs`} className="btn-secondary no-underline">
            Runs dashboard
          </Link>
        }
      />
      <form
        className="card mb-4 flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) setExtra((x) => [...x, typed.trim()]);
          setTyped("");
        }}
      >
        <div className="min-w-64 flex-1">
          <label className="label" htmlFor="run-id">
            Run ID
          </label>
          <input
            id="run-id"
            className="field font-mono"
            placeholder="run_…"
            aria-invalid={typed !== "" && !valid}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
          />
        </div>
        <button type="submit" className="btn-secondary" disabled={!valid}>
          Add run
        </button>
      </form>
      {list.isPending ? (
        <LoadingState label="Loading runs…" />
      ) : list.error ? (
        <ErrorState error={list.error} title="Could not load runs" />
      ) : runs.length === 0 ? (
        <EmptyState title="No runs yet">Reports appear after a run finishes. Paste a run ID above to download one.</EmptyState>
      ) : (
        <ul aria-label="Runs" className="m-0 flex list-none flex-col gap-2 p-0">
          {runs.map((r) => (
            <Downloads key={r} pid={pid} runId={r} />
          ))}
        </ul>
      )}
    </section>
  );
}
