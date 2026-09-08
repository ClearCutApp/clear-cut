import type { ReactElement } from "react";
import { Route, Routes } from "react-router";

import { RequireIdentity } from "./auth/RequireIdentity";
import { LandingView } from "./views/LandingView";
import { AuthView } from "./views/AuthView";
import { VerifyEmailView } from "./views/VerifyEmailView";
import { AppShell } from "./shell/AppShell";
import { ProjectLayout } from "./shell/ProjectLayout";
import { AnalyzeView } from "./views/AnalyzeView";
import { AskView } from "./views/AskView";
import { NotFoundView } from "./views/NotFoundView";
import { OverviewView } from "./views/OverviewView";
import { ProjectEntryView } from "./views/ProjectEntryView";
import { ProjectsView } from "./views/ProjectsView";
import { DocumentsView } from "./views/DocumentsView";
import { ReportsView } from "./views/ReportsView";
import { SearchView } from "./views/SearchView";
import { NotificationsView } from "./views/NotificationsView";
import { ActivityView } from "./views/ActivityView";
import { TeamView } from "./views/TeamView";
import { JoinWorkspaceView } from "./views/JoinWorkspaceView";
import { ProjectSettingsView } from "./views/ProjectSettingsView";
import { EditorView } from "./views/EditorView";
import { ScriptView } from "./views/ScriptView";

/**
 * The route table, one destination per file, and nothing else. The shell
 * frames every route; a project route adds `ProjectLayout`, which mounts
 * the project's data layer for the views under it.
 */
export function App(): ReactElement {
  return (
    <Routes>
      <Route index element={<LandingView />} />
      <Route path="login" element={<AuthView />} />
      <Route path="signup" element={<AuthView signup />} />
      <Route path="verify-email" element={<VerifyEmailView />} />
      <Route element={<RequireIdentity />}>
      <Route element={<AppShell />}>
        <Route path="projects" element={<ProjectsView />} />
        <Route path="team" element={<TeamView />} />
        <Route path="join" element={<JoinWorkspaceView />} />
        <Route path="projects/:projectId" element={<ProjectLayout />}>
          <Route index element={<ProjectEntryView />} />
          <Route path="clearances" element={<OverviewView />} />
          <Route path="analyze" element={<AnalyzeView />} />
          <Route path="documents" element={<DocumentsView />} />
          <Route path="reports" element={<ReportsView />} />
          <Route path="activity" element={<ActivityView />} />
          <Route path="notifications" element={<NotificationsView />} />
          <Route path="search" element={<SearchView />} />
          <Route path="settings" element={<ProjectSettingsView />} />
          <Route path="editor" element={<EditorView />} />
          <Route path="script" element={<ScriptView />} />
          <Route path="ask" element={<AskView />} />
        </Route>
        <Route path="*" element={<NotFoundView />} />
      </Route>
      </Route>
    </Routes>
  );
}
