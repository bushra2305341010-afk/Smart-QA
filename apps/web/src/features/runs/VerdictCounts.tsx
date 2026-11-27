import type { RunTotals } from "../../api/types";
import { VERDICTS, VERDICT_META } from "../../components/VerdictBadge";

/** Verdict counts from `RunOut.totals.verdicts` (0 when the Judge has not written any yet). */
export function verdictCounts(totals: unknown): Record<string, number> {
  const verdicts = (totals as RunTotals | null)?.verdicts ?? {};
  return Object.fromEntries(VERDICTS.map((v) => [v, Number(verdicts[v] ?? 0)]));
}

/** "Started" / "finished" times as local text; a dash when missing. */
export function when(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString();
}

/** Non-zero verdict counts as small coloured chips (colour + icon + word). */
export function VerdictCounts({ totals }: { totals: unknown }) {
  const counts = verdictCounts(totals);
  const shown = VERDICTS.filter((v) => counts[v]! > 0);
  if (shown.length === 0) return <span className="text-xs text-muted">No verdicts yet</span>;
  return (
    <ul className="m-0 flex list-none flex-wrap gap-1 p-0">
      {shown.map((v) => {
        const m = VERDICT_META[v];
        return (
          <li key={v} className={`inline-flex gap-1 rounded-full px-2 py-0.5 text-xs font-bold ${m.cls}`}>
            <span aria-hidden="true">{m.icon}</span>
            {counts[v]} {m.label}
          </li>
        );
      })}
    </ul>
  );
}

const RUN_STATUS: Record<string, string> = {
  queued: "○ Queued",
  running: "▶ Running",
  paused: "‖ Paused",
  completed: "✓ Completed",
  failed: "✕ Failed",
  cancelled: "⊘ Cancelled",
};

export function RunStatus({ status }: { status: string }) {
  const text = RUN_STATUS[status] ?? status;
  return <span className="inline-flex rounded-full border border-border px-2 py-0.5 text-xs font-semibold">{text}</span>;
}
