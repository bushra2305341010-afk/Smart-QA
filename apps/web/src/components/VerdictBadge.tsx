/** Verdict chip: always colour + icon + word, never colour alone (docs/05 §3.2). */
export type Verdict = "pass" | "fail" | "flaky" | "blocked" | "test_error" | "unable_to_verify";

const META: Record<Verdict, { label: string; icon: string; cls: string }> = {
  pass: { label: "Pass", icon: "✓", cls: "text-pass bg-pass-bg" },
  fail: { label: "Fail", icon: "✕", cls: "text-fail bg-fail-bg" },
  flaky: { label: "Flaky", icon: "⇄", cls: "text-flaky bg-flaky-bg" },
  blocked: { label: "Blocked", icon: "⊘", cls: "text-blocked bg-blocked-bg" },
  test_error: { label: "Test Error", icon: "🔧", cls: "text-testerr bg-testerr-bg" },
  unable_to_verify: { label: "Unable to Verify", icon: "?", cls: "text-uv bg-uv-bg" },
};

type Props = { verdict: Verdict; confidence?: "high" | "medium" | "low" };

export function VerdictBadge({ verdict, confidence }: Props) {
  const m = META[verdict];
  return (
    <span
      role="status"
      aria-label={`Verdict: ${m.label}${confidence ? `, ${confidence} confidence` : ""}`}
      className={`inline-flex gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-bold ${m.cls}`}
    >
      <span aria-hidden="true">{m.icon}</span>
      {m.label}
      {confidence ? <span>· {confidence[0]!.toUpperCase() + confidence.slice(1)}</span> : null}
    </span>
  );
}
