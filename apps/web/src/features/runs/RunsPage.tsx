import { PageHeader } from "../../components/PageHeader";
import { EmptyState } from "../../components/States";

/**
 * Placeholder route for the run dashboard (status tiles per verdict, live list over SSE,
 * evidence drawer). Run components belong in this folder.
 */
export function RunsPage() {
  return (
    <section>
      <PageHeader title="Runs" description="Live run dashboard with verdicts and evidence." />
      <EmptyState title="Run dashboard coming soon">
        Runs start after Gate 3. Live progress, verdicts and evidence will show here.
      </EmptyState>
    </section>
  );
}
