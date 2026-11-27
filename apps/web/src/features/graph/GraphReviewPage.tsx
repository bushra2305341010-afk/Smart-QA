import { useMemo, useState } from "react";
import { ApiError } from "../../api/client";
import { usePipelineEvent } from "../../api/projects";
import { useApproveGraph, useGraph, useGraphVersions, useReviewNode, type NodeReview } from "../../api/review";
import type { GraphOut, VersionOut } from "../../api/types";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { useHotkeys } from "../../hooks/useHotkeys";
import { useRequiredProjectId } from "../../hooks/useProjectId";
import { NodeDetail } from "./NodeDetail";

/** Gate 1: review every node of the Product Understanding Graph, then approve the version. */
export function GraphReviewPage() {
  const pid = useRequiredProjectId();
  const versions = useGraphVersions(pid);
  const [chosen, setChosen] = useState<string | undefined>();
  const versionId = chosen ?? versions.data?.[0]?.id;

  let body;
  if (versions.isPending) body = <LoadingState label="Loading graph versions…" />;
  else if (versions.error) body = <ErrorState error={versions.error} title="Could not load the graph" />;
  else if (!versionId) {
    body = (
      <EmptyState title="No graph yet">
        Upload a PRD or connect a repo on the Setup screen, then start the pipeline.
      </EmptyState>
    );
  } else {
    body = <VersionReview pid={pid} versionId={versionId} versions={versions.data} onChoose={setChosen} />;
  }
  return (
    <section>
      <PageHeader
        title="Graph review"
        description="Gate 1 · Check each fact against its source quote. Keys: J/K move, A approve, R reject."
      />
      {body}
    </section>
  );
}

type VersionProps = {
  pid: string;
  versionId: string;
  versions: VersionOut[];
  onChoose: (id: string) => void;
};

function VersionReview({ pid, versionId, versions, onChoose }: VersionProps) {
  const graph = useGraph(pid, versionId);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="label" htmlFor="graph-version">
            Version
          </label>
          <select id="graph-version" className="field" value={versionId} onChange={(e) => onChoose(e.target.value)}>
            {versions.map((v) => (
              <option key={v.id} value={v.id}>
                {`v${v.number} · ${v.status} · ${v.pending} pending of ${v.nodes}`}
              </option>
            ))}
          </select>
        </div>
      </div>
      {graph.isPending ? (
        <LoadingState label="Loading nodes…" />
      ) : graph.error ? (
        <ErrorState error={graph.error} title="Could not load this version" />
      ) : (
        <NodeReview pid={pid} graph={graph.data} />
      )}
    </div>
  );
}

function NodeReview({ pid, graph }: { pid: string; graph: GraphOut }) {
  const gv = graph.version.id;
  const review = useReviewNode(pid, gv);
  const approve = useApproveGraph(pid, gv);
  const reject = usePipelineEvent(pid);
  const [type, setType] = useState("");
  const [index, setIndex] = useState(0);
  const editable = graph.version.status === "draft";

  const types = useMemo(() => [...new Set(graph.nodes.map((n) => n.type))].sort(), [graph.nodes]);
  const nodes = useMemo(() => graph.nodes.filter((n) => !type || n.type === type), [graph.nodes, type]);
  const pending = graph.nodes.filter((n) => n.review_status === "pending").length;
  const node = nodes[Math.min(index, nodes.length - 1)];

  const decide = (r: NodeReview) => {
    if (!node) return;
    review.mutate({ nodeId: node.id, review: r }, { onSuccess: () => setIndex((i) => Math.min(i + 1, nodes.length - 1)) });
  };
  useHotkeys({
    j: () => setIndex((i) => Math.min(i + 1, nodes.length - 1)),
    k: () => setIndex((i) => Math.max(i - 1, 0)),
    a: () => editable && decide({ review_status: "approved" }),
    r: () => editable && decide({ review_status: "rejected" }),
  });

  const pendingIds = approve.error instanceof ApiError ? approve.error.details.pending_node_ids : undefined;

  return (
    <>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="label" htmlFor="node-type">
            Node type
          </label>
          <select
            id="node-type"
            className="field"
            value={type}
            onChange={(e) => {
              setType(e.target.value);
              setIndex(0);
            }}
          >
            <option value="">All types</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <p className="m-0 text-sm text-muted" aria-live="polite">
          {pending} of {graph.nodes.length} nodes pending
        </p>
        {editable ? (
          <div className="ml-auto flex gap-2">
            <button type="button" className="btn-danger" disabled={reject.isPending} onClick={() => reject.mutate("graph_rejected")}>
              Reject graph and rebuild
            </button>
            <button type="button" className="btn-primary" disabled={approve.isPending} onClick={() => approve.mutate()}>
              Approve graph
            </button>
          </div>
        ) : (
          <p className="m-0 ml-auto text-sm text-muted">This version is {graph.version.status}; it cannot be changed.</p>
        )}
      </div>
      {approve.isSuccess ? (
        <p role="status" className="m-0 text-sm text-accent">
          Graph approved. Planning starts next.
        </p>
      ) : null}
      {approve.error ? (
        <ErrorState
          error={approve.error}
          title={Array.isArray(pendingIds) ? `${pendingIds.length} nodes still need a decision` : "Graph not approved"}
        />
      ) : null}
      {reject.error ? <ErrorState error={reject.error} title="Could not reject the graph" /> : null}
      {review.error ? <ErrorState error={review.error} title="Decision not saved" /> : null}

      {nodes.length === 0 || !node ? (
        <EmptyState title="No nodes match this filter" />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
          <ul aria-label="Graph nodes" className="m-0 flex max-h-[70vh] list-none flex-col gap-1 overflow-auto p-0">
            {nodes.map((n, i) => (
              <li key={n.id}>
                <button
                  type="button"
                  aria-current={n.id === node.id ? "true" : undefined}
                  onClick={() => setIndex(i)}
                  className={`flex w-full items-center justify-between gap-2 rounded border bg-surface p-2 text-left text-sm ${
                    n.review_status === "pending" ? "border-dashed border-muted" : "border-border"
                  } ${n.id === node.id ? "ring-2 ring-primary" : ""}`}
                >
                  <span>
                    <span className="block text-xs text-muted">{n.type}</span>
                    {n.label}
                  </span>
                  <StatusBadge status={n.review_status} />
                </button>
              </li>
            ))}
          </ul>
          <NodeDetail node={node} editable={editable} busy={review.isPending} onDecide={decide} />
        </div>
      )}
    </>
  );
}
