import { useEffect, useState, type FormEvent } from "react";
import type { SegmentOut, TechniqueRow } from "../../api/types";

type Props = {
  segment: SegmentOut;
  editable: boolean;
  busy: boolean;
  onSave: (count: number) => void;
};

/** Planner priorities (packages/contracts/plan.py: Must / Should / Could). */
const PRIORITY: Record<string, string> = {
  must: "border-sev-high text-sev-high",
  should: "border-sev-medium text-sev-medium",
  could: "border-sev-low text-sev-low",
};

/** One journey: why this many cases (technique rows from code), and the human's approved count. */
export function SegmentRow({ segment, editable, busy, onSave }: Props) {
  const current = segment.approved_count ?? segment.suggested_count;
  const [value, setValue] = useState(String(current));
  useEffect(() => setValue(String(current)), [current]);
  const parsed = Number(value);
  const valid = value.trim() !== "" && Number.isInteger(parsed) && parsed >= 0 && parsed <= 500;
  const dirty = valid && parsed !== current;
  const edited = segment.approved_count != null && segment.approved_count !== segment.suggested_count;
  const rows = segment.rows as TechniqueRow[];
  const inputId = `count-${segment.id}`;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (dirty) onSave(parsed);
  };

  return (
    <tr className="border-b border-border align-top last:border-0">
      <th scope="row" className="p-2 text-left font-semibold">
        {segment.journey}
        <span
          className={`ml-2 inline-block rounded-full border px-2 text-xs font-semibold ${
            PRIORITY[segment.priority.toLowerCase()] ?? "border-border text-muted"
          }`}
        >
          {segment.priority}
        </span>
        <span className="block text-xs font-normal text-muted">Risk {segment.risk_score.toFixed(2)}</span>
      </th>
      <td className="p-2">
        <ul className="m-0 list-none p-0">
          {rows.map((r) => (
            <li key={`${r.technique}:${r.reason}`} className="text-sm">
              <span className="font-semibold">{r.count}</span> × {r.technique.replace(/_/g, " ")}
              <span className="block text-xs text-muted">{r.reason}</span>
            </li>
          ))}
        </ul>
        {segment.multiplier !== 1 ? (
          <p className="m-0 mt-1 text-xs text-muted">
            Base {segment.base_count} × risk multiplier {segment.multiplier}
          </p>
        ) : null}
        {segment.previous_decision ? (
          <p className="m-0 mt-1 text-xs text-muted">
            Last time: suggested {segment.previous_decision.suggested ?? "?"}, you approved{" "}
            {segment.previous_decision.approved ?? "?"}.
          </p>
        ) : null}
      </td>
      <td className="p-2 text-right">{segment.suggested_count}</td>
      <td className="p-2">
        {editable ? (
          <form onSubmit={submit} className="flex items-center gap-2">
            <label htmlFor={inputId} className="sr-only">
              Approved count for {segment.journey}
            </label>
            <input
              id={inputId}
              type="number"
              min={0}
              max={500}
              className={`field w-20 ${edited || dirty ? "border-primary" : ""}`}
              value={value}
              aria-invalid={!valid}
              onChange={(e) => setValue(e.target.value)}
            />
            {dirty ? (
              <button type="submit" className="btn-secondary" disabled={busy}>
                Save
              </button>
            ) : null}
          </form>
        ) : (
          <span>{current}</span>
        )}
        {edited ? <span className="mt-1 block text-xs text-primary">Edited from {segment.suggested_count}</span> : null}
      </td>
    </tr>
  );
}
