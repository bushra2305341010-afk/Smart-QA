import { useEffect, useState, type FormEvent } from "react";
import type { NodeOut } from "../../api/types";
import { CitationQuote } from "../../components/CitationQuote";
import { StatusBadge } from "../../components/StatusBadge";

type Props = {
  node: NodeOut;
  editable: boolean;
  busy: boolean;
  onDecide: (review: { review_status: "approved" | "rejected" } | { review_status: "edited"; label: string }) => void;
};

/** One node with every source quote behind it, and the approve / edit / reject actions. */
export function NodeDetail({ node, editable, busy, onDecide }: Props) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(node.label);
  useEffect(() => {
    setEditing(false);
    setLabel(node.label);
  }, [node.id, node.label]);

  const saveEdit = (e: FormEvent) => {
    e.preventDefault();
    onDecide({ review_status: "edited", label: label.trim() });
  };

  return (
    <article aria-labelledby="node-detail-title" className="card flex flex-col gap-3">
      <header>
        <p className="m-0 text-xs font-semibold uppercase text-muted">{node.type}</p>
        <h2 id="node-detail-title" className="m-0 text-lg font-semibold">
          {node.label}
        </h2>
        <StatusBadge status={node.review_status} />
      </header>
      <section aria-label="Source quotes" className="flex flex-col gap-2">
        {node.citations.length === 0 ? (
          <CitationQuote quote={null} status="unable_to_verify" reason="This node has no citation." />
        ) : (
          node.citations.map((c) => (
            <CitationQuote
              key={`${c.source_id}:${c.start_offset}`}
              quote={c.quote}
              status={c.status}
              file={c.file}
              page={c.page}
              line={c.line}
            />
          ))
        )}
      </section>
      {editable ? (
        editing ? (
          <form onSubmit={saveEdit} className="flex flex-col gap-2">
            <label className="label" htmlFor="node-label">
              Corrected label
            </label>
            <input
              id="node-label"
              className="field"
              required
              maxLength={500}
              value={label}
              onChange={(e) => setLabel(e.target.value)}
            />
            <div className="flex gap-2">
              <button type="submit" className="btn-primary" disabled={busy || !label.trim()}>
                Save edit
              </button>
              <button type="button" className="btn-secondary" onClick={() => setEditing(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-primary"
              aria-keyshortcuts="A"
              disabled={busy}
              onClick={() => onDecide({ review_status: "approved" })}
            >
              Approve node
            </button>
            <button type="button" className="btn-secondary" disabled={busy} onClick={() => setEditing(true)}>
              Edit label
            </button>
            <button
              type="button"
              className="btn-danger"
              aria-keyshortcuts="R"
              disabled={busy}
              onClick={() => onDecide({ review_status: "rejected" })}
            >
              Reject node
            </button>
          </div>
        )
      ) : null}
    </article>
  );
}
