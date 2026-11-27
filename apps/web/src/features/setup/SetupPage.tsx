import { useProject } from "../../api/projects";
import { PageHeader } from "../../components/PageHeader";
import { ErrorState } from "../../components/States";
import { useRequiredProjectId } from "../../hooks/useProjectId";
import { EnvironmentsPanel } from "./EnvironmentsPanel";
import { PipelineControls } from "./PipelineControls";
import { SourcesPanel } from "./SourcesPanel";

export function SetupPage() {
  const pid = useRequiredProjectId();
  const project = useProject(pid);
  if (project.error) return <ErrorState error={project.error} title="Could not open this project" />;
  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        title={project.data ? `Setup · ${project.data.name}` : "Setup"}
        description="Connect documents, code and the app under test, then start the pipeline."
      />
      <SourcesPanel pid={pid} />
      <EnvironmentsPanel pid={pid} />
      <PipelineControls pid={pid} />
    </section>
  );
}
