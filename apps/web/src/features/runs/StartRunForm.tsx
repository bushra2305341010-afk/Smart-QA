import { useState, type FormEvent } from "react";
import { useEnvironments, usePipeline } from "../../api/projects";
import { usePlans } from "../../api/review";
import { useStartRun } from "../../api/runs";
import { ErrorState } from "../../components/States";

/**
 * "Start regression run": POST /runs with an environment (default: the project's) and optional
 * journeys. Only allowed once the pipeline is `done`; the API still decides (409 shown as is).
 */
export function StartRunForm({ pid }: { pid: string }) {
  const pipeline = usePipeline(pid);
  const envs = useEnvironments(pid);
  const plans = usePlans(pid);
  const start = useStartRun(pid);
  const [envId, setEnvId] = useState("");
  const [journeys, setJourneys] = useState<string[]>([]);

  const current = pipeline.data?.current;
  const done = current?.stage === "done";
  const plan = plans.data?.find((p) => p.status === "approved") ?? plans.data?.[0];
  const names = [...new Set((plan?.segments ?? []).map((s) => s.journey))];

  const toggle = (name: string) =>
    setJourneys((js) => (js.includes(name) ? js.filter((j) => j !== name) : [...js, name]));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    start.mutate({ env_id: envId || null, journeys });
  };

  return (
    <form onSubmit={submit} aria-labelledby="start-run-heading" className="card mb-4 flex flex-col gap-3">
      <h2 id="start-run-heading" className="m-0 text-lg font-semibold">
        Start regression run
      </h2>
      {!done ? (
        <p id="start-run-why" className="m-0 text-sm text-muted">
          {current
            ? `Regression runs start when the pipeline is done. It is now at "${current.stage}" (${current.status.replace(/_/g, " ")}).`
            : "Regression runs start when the pipeline is done. The pipeline has not started yet."}
        </p>
      ) : null}
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-56">
          <label className="label" htmlFor="run-env">
            Environment
          </label>
          <select id="run-env" className="field" value={envId} onChange={(e) => setEnvId(e.target.value)}>
            <option value="">Project default</option>
            {(envs.data ?? []).map((env) => (
              <option key={env.id} value={env.id}>
                {env.name} ({env.kind})
              </option>
            ))}
          </select>
        </div>
        {names.length > 0 ? (
          <fieldset className="m-0 min-w-0 flex-1 border-0 p-0">
            <legend className="label">Journeys (none ticked = all)</legend>
            <div className="flex flex-wrap gap-3 text-sm">
              {names.map((name) => (
                <label key={name} className="inline-flex items-center gap-1">
                  <input type="checkbox" checked={journeys.includes(name)} onChange={() => toggle(name)} />
                  {name}
                </label>
              ))}
            </div>
          </fieldset>
        ) : null}
        <button
          type="submit"
          className="btn-primary"
          disabled={!done || start.isPending}
          aria-describedby={!done ? "start-run-why" : undefined}
        >
          {start.isPending ? "Starting…" : "Start run"}
        </button>
      </div>
      {envs.error ? <ErrorState error={envs.error} title="Could not load environments" /> : null}
      {start.error ? <ErrorState error={start.error} title="Run not started" /> : null}
      {start.isSuccess ? (
        <p role="status" className="m-0 text-sm text-accent">
          Run requested ({start.data.stage}, {start.data.status}). It appears below once compiled.
        </p>
      ) : null}
    </form>
  );
}
