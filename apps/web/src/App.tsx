import { VerdictBadge } from "./components/VerdictBadge";

export function App() {
  return (
    <main style={{ padding: 32, maxWidth: 960, margin: "0 auto" }}>
      <h1>Smart Autonomous QA</h1>
      <p style={{ color: "var(--text-muted)" }}>
        Web app scaffold. Screens are built from docs/05-frontend-ui-design.md §5.
      </p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <VerdictBadge verdict="pass" confidence="high" />
        <VerdictBadge verdict="fail" confidence="high" />
        <VerdictBadge verdict="flaky" />
        <VerdictBadge verdict="blocked" />
        <VerdictBadge verdict="test_error" />
        <VerdictBadge verdict="unable_to_verify" />
      </div>
    </main>
  );
}
