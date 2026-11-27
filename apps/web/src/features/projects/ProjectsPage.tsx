import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useCreateProject, useProjects } from "../../api/projects";
import { PageHeader } from "../../components/PageHeader";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";

const ROLE: Record<string, string> = {
  owner: "Owner",
  qa_lead: "QA Lead",
  tester: "Tester",
  developer: "Developer",
  viewer: "Viewer",
};

export function ProjectsPage() {
  const projects = useProjects();
  const create = useCreateProject();
  const navigate = useNavigate();
  const [name, setName] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate(name.trim(), { onSuccess: (p) => navigate(`/projects/${p.id}/setup`) });
  };

  return (
    <section>
      <PageHeader title="Projects" description="Each project is one product under test." />
      <form onSubmit={submit} className="card mb-4 flex flex-wrap items-end gap-2">
        <div className="min-w-64 flex-1">
          <label className="label" htmlFor="project-name">
            New project name
          </label>
          <input
            id="project-name"
            className="field"
            required
            maxLength={200}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <button type="submit" className="btn-primary" disabled={create.isPending || !name.trim()}>
          Create project
        </button>
        {create.error ? (
          <div className="w-full">
            <ErrorState error={create.error} title="Could not create the project" />
          </div>
        ) : null}
      </form>

      {projects.isPending ? (
        <LoadingState label="Loading projects…" />
      ) : projects.error ? (
        <ErrorState error={projects.error} title="Could not load projects" />
      ) : projects.data.length === 0 ? (
        <EmptyState title="No projects yet">Create one above, then upload a PRD or connect a repo.</EmptyState>
      ) : (
        <table className="w-full border-collapse overflow-hidden rounded-card bg-surface text-sm">
          <caption className="sr-only">Your projects</caption>
          <thead>
            <tr className="border-b border-border text-left text-muted">
              <th scope="col" className="p-2">Name</th>
              <th scope="col" className="p-2">Your role</th>
              <th scope="col" className="p-2">Stage</th>
              <th scope="col" className="p-2">Created</th>
            </tr>
          </thead>
          <tbody>
            {projects.data.map((p) => (
              <tr key={p.id} className="border-b border-border last:border-0 hover:bg-surface-2">
                <td className="p-2">
                  <Link className="font-semibold text-primary underline" to={`/projects/${p.id}/setup`}>
                    {p.name}
                  </Link>
                </td>
                <td className="p-2">{ROLE[p.role] ?? p.role}</td>
                <td className="p-2">{p.stage ? p.stage.replace(/_/g, " ") : "not started"}</td>
                <td className="p-2">{new Date(p.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
