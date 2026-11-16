/** Verdict chip: always colour + icon + word, never colour alone (docs/05 §3.2). */
export type Verdict = "pass" | "fail" | "flaky" | "blocked" | "test_error" | "unable_to_verify";

const META: Record<Verdict, { label: string; icon: string; fg: string; bg: string }> = {
  pass: { label: "Pass", icon: "✓", fg: "var(--pass)", bg: "var(--pass-bg)" },
  fail: { label: "Fail", icon: "✕", fg: "var(--fail)", bg: "var(--fail-bg)" },
  flaky: { label: "Flaky", icon: "⇄", fg: "var(--flaky)", bg: "var(--flaky-bg)" },
  blocked: { label: "Blocked", icon: "⊘", fg: "var(--blocked)", bg: "var(--blocked-bg)" },
  test_error: { label: "Test Error", icon: "🔧", fg: "var(--testerr)", bg: "var(--testerr-bg)" },
  unable_to_verify: { label: "Unable to Verify", icon: "?", fg: "var(--uv)", bg: "var(--uv-bg)" },
};

type Props = { verdict: Verdict; confidence?: "high" | "medium" | "low" };

export function VerdictBadge({ verdict, confidence }: Props) {
  const m = META[verdict];
  return (
    <span
      role="status"
      aria-label={`Verdict: ${m.label}${confidence ? `, ${confidence} confidence` : ""}`}
      style={{
        color: m.fg, background: m.bg, borderRadius: 999, padding: "2px 10px",
        fontWeight: 700, fontSize: 12, display: "inline-flex", gap: 6,
      }}
    >
      <span aria-hidden="true">{m.icon}</span>
      {m.label}
      {confidence ? <span>· {confidence[0]!.toUpperCase() + confidence.slice(1)}</span> : null}
    </span>
  );
}
