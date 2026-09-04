import type { ReactElement } from "react";
import { Route, Routes } from "react-router";

import { AppShell } from "./shell/AppShell";
import { ProjectLayout } from "./shell/ProjectLayout";
import { AnalyzeView } from "./views/AnalyzeView";
import { AskView } from "./views/AskView";
import { NotFoundView } from "./views/NotFoundView";
import { OverviewView } from "./views/OverviewView";
import { ProjectsView } from "./views/ProjectsView";
import { ScriptView } from "./views/ScriptView";

/**
 * The route table, one destination per file, and nothing else. The shell
 * frames every route; a project route adds `ProjectLayout`, which mounts
 * the project's data layer for the views under it.
 */
export function App(): ReactElement {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<ProjectsView />} />
        <Route path="projects/:projectId" element={<ProjectLayout />}>
          <Route index element={<OverviewView />} />
          <Route path="analyze" element={<AnalyzeView />} />
          <Route path="script" element={<ScriptView />} />
          <Route path="ask" element={<AskView />} />
        </Route>
        <Route path="*" element={<NotFoundView />} />
      </Route>
    </Routes>
  );
}
