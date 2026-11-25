import { Navigate, Route, Routes } from "react-router-dom";
import { LoginPage } from "../features/auth/LoginPage";
import { RegisterPage } from "../features/auth/RegisterPage";
import { BugReviewPage } from "../features/bugs/BugReviewPage";
import { CaseReviewPage } from "../features/cases/CaseReviewPage";
import { GraphReviewPage } from "../features/graph/GraphReviewPage";
import { PlanPage } from "../features/plan/PlanPage";
import { ProjectsPage } from "../features/projects/ProjectsPage";
import { ReportsPage } from "../features/reports/ReportsPage";
import { RunsPage } from "../features/runs/RunsPage";
import { SecurityPage } from "../features/settings/SecurityPage";
import { SetupPage } from "../features/setup/SetupPage";
import { AppShell } from "./AppShell";
import { NotFoundPage } from "./NotFoundPage";
import { RequireAuth } from "./RequireAuth";

/** Every screen's route. Project screens live under /projects/:pid so the switcher keeps the tab. */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/projects" replace />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="settings/security" element={<SecurityPage />} />
        <Route path="projects/:pid">
          <Route index element={<Navigate to="setup" replace />} />
          <Route path="setup" element={<SetupPage />} />
          <Route path="graph" element={<GraphReviewPage />} />
          <Route path="plan" element={<PlanPage />} />
          <Route path="cases" element={<CaseReviewPage />} />
          <Route path="runs" element={<RunsPage />} />
          <Route path="bugs" element={<BugReviewPage />} />
          <Route path="reports" element={<ReportsPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
