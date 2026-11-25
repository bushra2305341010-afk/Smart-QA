import { usePipeline, usePipelineEvent } from "../../api/projects";
import { ErrorState, LoadingState } from "../../components/States";

const ACTIVE = new Set(["queued", "running", "awaiting_approval", "failed"]);

/** Start / retry / cancel the pipeline (POST /pipeline/events). Gate decisions live on their screens. */
export function PipelineControls({ pid }: { pid: string }) {
  const pipeline = usePipeline(pid);
  const event = usePipelineEvent(pid);
  if (pipeline.isPending) return <LoadingState label="Loading pipeline…" />;
  if (pipeline.error) return <ErrorState error={pipeline.error} title="Could not load the pipeline" />;
  const current = pipeline.data.current;
  const canStart = !current || current.status === "done" || current.status === "cancelled";
  return (
    <section aria-labelledby="pipeline-heading" className="card">
      <h2 id="pipeline-heading" className="m-0 mb-2 text-lg font-semibold">
        Pipeline
      </h2>
      <p className="m-0 mb-3 text-sm" aria-live="polite">
        {current
          ? `Stage: ${current.stage.replace(/_/g, " ")} · ${current.status.replace(/_/g, " ")}`
          : "Not started. Add sources first, then start."}
      </p>
      <div className="flex flex-wrap gap-2">
        {canStart ? (
          <button type="button" className="btn-primary" disabled={event.isPending} onClick={() => event.mutate("start")}>
            Start pipeline
          </button>
        ) : null}
        {current?.status === "failed" ? (
          <button type="button" className="btn-secondary" disabled={event.isPending} onClick={() => event.mutate("retry")}>
            Retry stage
          </button>
        ) : null}
        {current && ACTIVE.has(current.status) ? (
          <button type="button" className="btn-danger" disabled={event.isPending} onClick={() => event.mutate("cancel")}>
            Cancel pipeline
          </button>
        ) : null}
      </div>
      {event.error ? (
        <div className="mt-2">
          <ErrorState error={event.error} title="Pipeline refused the action" />
        </div>
      ) : null}
    </section>
  );
}
