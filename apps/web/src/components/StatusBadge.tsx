/** Review / lifecycle status as a word plus icon (never colour alone). */
const META: Record<string, { label: string; icon: string; cls: string }> = {
  pending: { label: "Pending", icon: "○", cls: "border-border text-muted" },
  draft: { label: "Draft", icon: "○", cls: "border-border text-muted" },
  approved: { label: "Approved", icon: "✓", cls: "border-accent text-accent" },
  confirmed: { label: "Confirmed", icon: "✓", cls: "border-accent text-accent" },
  filed: { label: "Filed", icon: "↗", cls: "border-accent text-accent" },
  edited: { label: "Edited", icon: "✎", cls: "border-primary text-primary" },
  rejected: { label: "Rejected", icon: "✕", cls: "border-danger text-danger" },
  dismissed: { label: "Dismissed", icon: "✕", cls: "border-danger text-danger" },
};

export function StatusBadge({ status }: { status: string }) {
  const m = META[status] ?? { label: status, icon: "•", cls: "border-border text-muted" };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold ${m.cls}`}>
      <span aria-hidden="true">{m.icon}</span>
      {m.label}
    </span>
  );
}
