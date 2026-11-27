/** This month's model spend against the project budget (GET /projects/{id}/costs). */
type Props = { spent: string; cap: string };

function money(v: number): string {
  return `$${v.toFixed(2)}`;
}

export function CostMeter({ spent, cap }: Props) {
  const used = Number(spent);
  const limit = Number(cap);
  const pct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const tone = pct >= 90 ? "bg-danger" : pct >= 75 ? "bg-flaky" : "bg-accent";
  const label = `Model spend this month: ${money(used)} of ${money(limit)}`;
  return (
    <div className="flex items-center gap-2 text-xs text-muted">
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-valuetext={`${pct}% of budget used`}
        className="h-2 w-24 overflow-hidden rounded-full bg-surface-2"
      >
        <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <span aria-hidden="true">
        {money(used)} / {money(limit)}
      </span>
    </div>
  );
}
