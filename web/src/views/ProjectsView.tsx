import type { ReactElement } from "react";

import { EmptyState } from "../components/atoms/EmptyState";
import { readRecentProjects } from "../state/recentProjects";

/**
 * The landing view. There is no project resource on the server, so the
 * only list this browser can show is the projects it opened itself; the
 * open form and that list arrive with the projects feature.
 */
export function ProjectsView(): ReactElement {
  const recent = readRecentProjects();
  return (
    <section className="projects">
      <h1>Projects</h1>
      {recent.length === 0 && (
        <EmptyState title="No projects opened in this browser yet." />
      )}
    </section>
  );
}
