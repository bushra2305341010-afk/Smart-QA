import { useNavigate } from "react-router-dom";
import { useProjects } from "../api/projects";
import { useProjectTab } from "../hooks/useProjectId";

/** Switch project while staying on the same screen (graph → graph). */
export function ProjectSwitcher({ current }: { current: string | undefined }) {
  const projects = useProjects();
  const tab = useProjectTab();
  const navigate = useNavigate();
  return (
    <div className="flex items-center gap-2">
      <label htmlFor="project-switcher" className="text-sm font-medium">
        Project
      </label>
      <select
        id="project-switcher"
        className="field w-48"
        value={current ?? ""}
        disabled={projects.isPending}
        onChange={(e) => navigate(e.target.value ? `/projects/${e.target.value}/${tab}` : "/projects")}
      >
        <option value="">{projects.isPending ? "Loading…" : "All projects"}</option>
        {(projects.data ?? []).map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
    </div>
  );
}
