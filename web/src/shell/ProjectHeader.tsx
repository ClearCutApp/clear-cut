import type { ReactElement } from "react";
import { Link } from "react-router";

import { useProject } from "../state/ProjectContext";
import { jurisdictionName } from "../theme/jurisdictions";

/**
 * What the app can say about a project: its id, the jurisdiction it is
 * analysed under, and the script version when an analysis ran in this
 * session. Title, format, status and "updated" have no project resource
 * behind them (Missing API registry) and are not drawn.
 */
export function ProjectHeader(): ReactElement {
  const { projectId, jurisdictionCode, analysis } = useProject();
  const analyzePath = `/projects/${encodeURIComponent(projectId)}/analyze`;
  return (
    <header className="project-header">
      <div className="project-header__identity">
        <h1 className="project-header__title">{projectId}</h1>
        <p className="project-header__meta">
          <span>{jurisdictionName(jurisdictionCode)}</span>
          {analysis !== null && <span>Script v{analysis.version}</span>}
        </p>
      </div>
      <Link className="button button--primary" to={analyzePath}>
        {analysis === null ? "Run analysis" : "Upload new version"}
      </Link>
    </header>
  );
}
