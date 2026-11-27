import { useNavigate } from "react-router-dom";
import { useLogout, useMe } from "../api/auth";
import { useCosts, usePipeline } from "../api/projects";
import { useProjectEvents } from "../api/runs";
import { CostMeter } from "../components/CostMeter";
import { StageStepper } from "../components/StageStepper";
import { useProjectId } from "../hooks/useProjectId";
import { ProjectSwitcher } from "./ProjectSwitcher";
import { ThemeToggle } from "./ThemeToggle";

function ProjectStatus({ pid }: { pid: string }) {
  const live = useProjectEvents(pid);
  const pipeline = usePipeline(pid, live ? false : 10_000);
  const costs = useCosts(pid);
  return (
    <>
      <StageStepper current={pipeline.data?.current} />
      {costs.data ? <CostMeter spent={costs.data.month.spent_usd} cap={costs.data.month.cap_usd} /> : null}
    </>
  );
}

export function TopBar() {
  const pid = useProjectId();
  const me = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  return (
    <header className="flex flex-wrap items-center gap-4 border-b border-border bg-surface px-4 py-2">
      <ProjectSwitcher current={pid} />
      {pid ? <ProjectStatus pid={pid} /> : null}
      <div className="ml-auto flex items-center gap-2 text-sm">
        <ThemeToggle />
        {me.data ? <span className="text-muted">{me.data.email}</span> : null}
        <button
          type="button"
          className="btn-secondary"
          onClick={() => logout.mutate(undefined, { onSettled: () => navigate("/login") })}
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
