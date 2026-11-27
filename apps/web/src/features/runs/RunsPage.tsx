import { Link } from "react-router-dom";
import { useRuns } from "../../api/runs";
import { PageHeader } from "../../components/PageHeader";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { useRequiredProjectId } from "../../hooks/useProjectId";
import { StartRunForm } from "./StartRunForm";
import { RunStatus, VerdictCounts, when } from "./VerdictCounts";

/** Run list (newest first) and the regression-run form. Live via `useProjectEvents` in the top bar. */
export function RunsPage() {
  const pid = useRequiredProjectId();
  const runs = useRuns(pid);
  let body;
  if (runs.isPending) body = <LoadingState label="Loading runs…" />;
  else if (runs.error) body = <ErrorState error={runs.error} title="Could not load runs" />;
  else if (runs.data.items.length === 0) {
    body = (
      <EmptyState title="No runs yet">
        The first run starts after Gate 3 (case review). Regression runs can be started here once the pipeline is done.
      </EmptyState>
    );
  } else {
    body = (
      <div className="card overflow-x-auto p-0">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">Runs, newest first</caption>
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted">
              <th scope="col" className="p-2">Run</th>
              <th scope="col" className="p-2">Status</th>
              <th scope="col" className="p-2">Environment</th>
              <th scope="col" className="p-2">Started</th>
              <th scope="col" className="p-2">Finished</th>
              <th scope="col" className="p-2">Verdicts</th>
            </tr>
          </thead>
          <tbody>
            {runs.data.items.map((r) => (
              <tr key={r.id} className="border-b border-border last:border-0">
                <td className="p-2">
                  <Link to={`/projects/${pid}/runs/${r.id}`} className="font-mono text-primary underline">
                    {r.id.slice(0, 12)}…<span className="sr-only"> open run {r.id}</span>
                  </Link>
                </td>
                <td className="p-2">
                  <RunStatus status={r.status} />
                </td>
                <td className="p-2">{r.env_name}</td>
                <td className="p-2">{when(r.started_at)}</td>
                <td className="p-2">{when(r.finished_at)}</td>
                <td className="p-2">
                  <VerdictCounts totals={r.totals} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {runs.data.next_cursor ? <p className="m-0 p-2 text-xs text-muted">Showing the latest 50 runs.</p> : null}
      </div>
    );
  }
  return (
    <section>
      <PageHeader title="Runs" description="Every run with its verdicts. Open a run for live progress and evidence." />
      <StartRunForm pid={pid} />
      {body}
    </section>
  );
}
