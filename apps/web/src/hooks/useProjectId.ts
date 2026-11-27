import { useMatch } from "react-router-dom";

/** The open project's id from the URL (`/projects/:pid/...`), or undefined outside a project. */
export function useProjectId(): string | undefined {
  const match = useMatch("/projects/:pid/*");
  return match?.params.pid;
}

/** Like useProjectId, for screens that only render inside a project route. */
export function useRequiredProjectId(): string {
  const pid = useProjectId();
  if (!pid) throw new Error("This screen needs a project in the URL");
  return pid;
}

/** The project sub-page (`setup`, `graph`, ...) so the switcher can keep it. */
export function useProjectTab(): string {
  const match = useMatch("/projects/:pid/:tab/*");
  return match?.params.tab ?? "setup";
}
