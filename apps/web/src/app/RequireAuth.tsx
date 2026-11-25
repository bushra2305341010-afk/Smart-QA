import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useMe } from "../api/auth";
import { ApiError } from "../api/client";
import { ErrorState, LoadingState } from "../components/States";

/** Shows children only to a signed-in user; otherwise sends them to /login and back afterwards. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const me = useMe();
  const location = useLocation();
  if (me.isPending || (me.isFetching && me.error)) {
    return (
      <main className="p-8">
        <LoadingState label="Checking your session…" />
      </main>
    );
  }
  if (me.error instanceof ApiError && me.error.status === 401) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (me.error) {
    return (
      <main className="p-8">
        <ErrorState error={me.error} title="Could not load your session" />
      </main>
    );
  }
  return <>{children}</>;
}
