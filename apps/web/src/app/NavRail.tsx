import { NavLink } from "react-router-dom";
import { useProjectId } from "../hooks/useProjectId";

type Item = { to: string; label: string; icon: string; end?: boolean };

const PROJECT_ITEMS: Item[] = [
  { to: "setup", label: "Setup", icon: "⚙" },
  { to: "graph", label: "Graph", icon: "◈" },
  { to: "plan", label: "Plan", icon: "▤" },
  { to: "cases", label: "Cases", icon: "☰" },
  { to: "runs", label: "Runs", icon: "▶" },
  { to: "bugs", label: "Bugs", icon: "✱" },
  { to: "reports", label: "Reports", icon: "⇩" },
];

function RailLink({ to, label, icon, end }: Item) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `flex flex-col items-center gap-0.5 rounded px-1 py-2 text-[11px] text-sidebar-text no-underline hover:bg-white/10 ${
          isActive ? "bg-white/15 font-semibold" : ""
        }`
      }
    >
      <span aria-hidden="true" className="text-lg leading-none">
        {icon}
      </span>
      {label}
    </NavLink>
  );
}

/** 64px navigation rail; project screens appear once a project is open. */
export function NavRail() {
  const pid = useProjectId();
  return (
    <nav aria-label="Main" className="flex w-16 shrink-0 flex-col gap-1 bg-sidebar p-1">
      <RailLink to="/projects" label="Projects" icon="▦" end />
      {pid ? PROJECT_ITEMS.map((i) => <RailLink key={i.to} {...i} to={`/projects/${pid}/${i.to}`} />) : null}
      <div className="mt-auto">
        <RailLink to="/settings/security" label="Security" icon="🔑" />
      </div>
    </nav>
  );
}
