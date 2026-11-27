import { Outlet } from "react-router-dom";
import { NavRail } from "./NavRail";
import { TopBar } from "./TopBar";

/** Nav rail · top bar (switcher, stepper, cost meter, user) · page (docs/05 §4). */
export function AppShell() {
  return (
    <div className="flex min-h-screen bg-bg text-text">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-10 focus:rounded focus:bg-surface focus:p-2"
      >
        Skip to content
      </a>
      <NavRail />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main id="main" tabIndex={-1} className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
