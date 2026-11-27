import { useCallback, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useRun } from "../../api/runs";
import type { CaseRow, RunDetail, RunTotals } from "../../api/types";
import { EvidenceDrawer } from "../../components/EvidenceDrawer";
import { PageHeader } from "../../components/PageHeader";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { VERDICTS, VERDICT_META, VerdictBadge, isVerdict, type Verdict } from "../../components/VerdictBadge";
import { useRequiredProjectId } from "../../hooks/useProjectId";
import { RunStatus, verdictCounts, when } from "./VerdictCounts";

type Filter = Verdict | "all" | "pending";

/** One run: verdict tiles, live progress (SSE patches the query), case table and evidence drawer. */
export function RunDetailPage() {
  const pid = useRequiredProjectId();
  const { runId = "" } = useParams();
  const run = useRun(pid, runId);
  let body;
  if (run.isPending) body = <LoadingState label="Loading run…" />;
  else if (run.error) body = <ErrorState error={run.error} title="Could not load the run" />;
  else body = <RunView pid={pid} run={run.data} />;
  return (
    <section>
      <PageHeader
        title="Run"
        description={<span className="font-mono">{runId}</span>}
        actions={
          <Link to={`/projects/${pid}/runs`} className="btn-secondary no-underline">
            All runs
          </Link>
        }
      />
      {body}
    </section>
  );
}

function RunView({ pid, run }: { pid: string; run: RunDetail }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [onlyUv, setOnlyUv] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const close = useCallback(() => setOpenId(null), []);

  const counts = verdictCounts(run.totals);
  const total = Number((run.totals as RunTotals).cases ?? run.cases.length) || run.cases.length;
  const judged = run.cases.filter((c) => c.verdict !== null).length;
  const active = onlyUv ? "unable_to_verify" : filter;
  const rows = useMemo(
    () =>
      run.cases.filter((c) =>
        active === "all" ? true : active === "pending" ? c.verdict === null : c.verdict === active,
      ),
    [run.cases, active],
  );
  const open = run.cases.find((c) => c.case_id === openId) ?? null;

  return (
    <div className="flex flex-col gap-4">
      <div className="card flex flex-wrap items-center gap-4 text-sm">
        <RunStatus status={run.status} />
        <span>
          Environment <span className="font-semibold">{run.env_name}</span>
        </span>
        <span className="text-muted">Started {when(run.started_at)}</span>
        <span className="text-muted">Finished {when(run.finished_at)}</span>
        <div className="flex min-w-48 flex-1 items-center gap-2">
          <label htmlFor="run-progress" className="text-xs text-muted">
            Judged
          </label>
          <progress id="run-progress" className="h-2 flex-1" max={Math.max(total, 1)} value={judged} />
          <span aria-live="polite" className="text-xs">
            {judged} of {total}
          </span>
        </div>
      </div>

      <ul aria-label="Verdict totals" className="m-0 grid list-none grid-cols-2 gap-2 p-0 sm:grid-cols-3 lg:grid-cols-6">
        {VERDICTS.map((v) => {
          const m = VERDICT_META[v];
          const pressed = active === v;
          return (
            <li key={v}>
              <button
                type="button"
                aria-pressed={pressed}
                onClick={() => {
                  setOnlyUv(false);
                  setFilter(pressed ? "all" : v);
                }}
                className={`flex w-full flex-col items-start rounded-card border p-3 text-left ${m.cls} ${
                  pressed ? "border-current ring-2 ring-primary" : "border-transparent"
                }`}
              >
                <span className="text-2xl font-bold">{counts[v]}</span>
                <span className="text-xs font-semibold">
                  <span aria-hidden="true">{m.icon} </span>
                  {m.label}
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label className="label" htmlFor="verdict-filter">
            Verdict
          </label>
          <select
            id="verdict-filter"
            className="field"
            value={filter}
            disabled={onlyUv}
            onChange={(e) => setFilter(e.target.value as Filter)}
          >
            <option value="all">All</option>
            {VERDICTS.map((v) => (
              <option key={v} value={v}>
                {VERDICT_META[v].label}
              </option>
            ))}
            <option value="pending">No verdict yet</option>
          </select>
        </div>
        <label className="inline-flex items-center gap-2 text-sm">
          <input type="checkbox" checked={onlyUv} onChange={(e) => setOnlyUv(e.target.checked)} />
          Only Unable to Verify (needs a human)
        </label>
        <p className="m-0 ml-auto text-xs text-muted" aria-live="polite">
          {rows.length} of {run.cases.length} cases
        </p>
      </div>

      {run.cases.length === 0 ? (
        <EmptyState title="No results yet">Cases appear here as the runner reports them.</EmptyState>
      ) : rows.length === 0 ? (
        <EmptyState title="No cases match this filter" />
      ) : (
        <CaseTable rows={rows} onOpen={setOpenId} />
      )}

      {open ? <EvidenceDrawer pid={pid} row={open} onClose={close} /> : null}
    </div>
  );
}

function CaseTable({ rows, onOpen }: { rows: CaseRow[]; onOpen: (id: string) => void }) {
  return (
    <div className="card overflow-x-auto p-0">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">Cases in this run</caption>
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted">
            <th scope="col" className="p-2">Case</th>
            <th scope="col" className="p-2">Title</th>
            <th scope="col" className="p-2">Verdict</th>
            <th scope="col" className="p-2">Confidence</th>
            <th scope="col" className="p-2">Rule</th>
            <th scope="col" className="p-2">Attempts</th>
            <th scope="col" className="p-2">Blocked</th>
            <th scope="col" className="p-2">
              <span className="sr-only">Evidence</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.case_id} className="border-b border-border align-top last:border-0">
              <td className="p-2 font-mono text-xs">{c.code}</td>
              <td className="p-2">
                {c.title}
                {c.verdict === "unable_to_verify" ? (
                  <span className="block text-xs font-semibold text-uv">Needs a human{c.reason ? `: ${c.reason}` : ""}</span>
                ) : null}
              </td>
              <td className="p-2">
                {isVerdict(c.verdict) ? <VerdictBadge verdict={c.verdict} /> : <span className="text-xs text-muted">{c.status ?? "pending"}</span>}
              </td>
              <td className="p-2">{c.level ?? "—"}</td>
              <td className="p-2 font-mono text-xs">{c.rule ?? "—"}</td>
              <td className="p-2">{c.attempts}</td>
              <td className="p-2">{c.blocked ?? "—"}</td>
              <td className="p-2">
                <button type="button" className="btn-secondary" onClick={() => onOpen(c.case_id)}>
                  Evidence<span className="sr-only"> for {c.code}</span>
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
