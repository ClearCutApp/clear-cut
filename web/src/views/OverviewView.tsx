import type { ReactElement } from "react";
import { Link } from "react-router";

import { EmptyState } from "../components/atoms/EmptyState";
import { ErrorNotice } from "../components/atoms/ErrorNotice";
import { useProject } from "../state/ProjectContext";

/**
 * The project's tracker. Reads the data layer's three states honestly:
 * loading while the mount GET is out, the server's own sentence when it
 * fails, and a worded empty state with the way out when no analysis ever
 * ran. Stats, filters and the grouped table arrive with the tracker
 * feature.
 */
export function OverviewView(): ReactElement {
  const { projectId, tracker, trackerError } = useProject();
  const analyzePath = `/projects/${encodeURIComponent(projectId)}/analyze`;
  return (
    <section className="tracker">
      <h2>Overview</h2>
      <ErrorNotice message={trackerError} />
      {tracker === null && trackerError === null && (
        <p>Loading the tracker for this project.</p>
      )}
      {tracker !== null && tracker.length === 0 && (
        <EmptyState title="No analysis has run yet for this project.">
          <Link to={analyzePath}>Run analysis</Link>
        </EmptyState>
      )}
    </section>
  );
}
