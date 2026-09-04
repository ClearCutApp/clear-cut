import type { ReactElement } from "react";
import { Link } from "react-router";

import { EmptyState } from "../components/atoms/EmptyState";
import { useProject } from "../state/ProjectContext";

/**
 * The script with its findings. An analysis lives in the session only
 * (there is no script resource to read back), so after a reload this view
 * says so and points at the way to run one. Scenes, highlights and the
 * findings rail arrive with the script feature.
 */
export function ScriptView(): ReactElement {
  const { projectId, analysis } = useProject();
  const analyzePath = `/projects/${encodeURIComponent(projectId)}/analyze`;
  return (
    <section className="script">
      <h2>Script</h2>
      {analysis === null && (
        <EmptyState title="No analysis is loaded in this session.">
          <Link to={analyzePath}>Run analysis</Link>
        </EmptyState>
      )}
    </section>
  );
}
