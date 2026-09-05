import type { ReactElement } from "react";
import { Link } from "react-router";

import { ErrorNotice } from "../components/atoms/ErrorNotice";
import { useProject } from "../state/ProjectContext";
import { jurisdictionName } from "../theme/jurisdictions";

/**
 * What the app can say about a project: its title once the project resource
 * answers, its id either way, the jurisdiction it is cleared against, and
 * the version of the newest stored script.
 *
 * The id stays on screen even under a title, because it is the value every
 * other screen and every support conversation names the project by. Format,
 * status, poster, team and "updated 2h ago" are in the design and in no
 * response, so they are not drawn.
 */
export function ProjectHeader(): ReactElement {
  const { projectId, project, projectError, jurisdictionCode, analysis } = useProject();
  const analyzePath = `/projects/${encodeURIComponent(projectId)}/analyze`;
  return (
    <header className="project-header">
      <div className="project-header__identity">
        <h1 className="project-header__title">{project?.title ?? projectId}</h1>
        <p className="project-header__meta">
          <span>{jurisdictionName(jurisdictionCode)}</span>
          {analysis !== null && <span>Script v{analysis.version}</span>}
          {project !== null && <span className="project-header__id">{projectId}</span>}
        </p>
        <ErrorNotice message={projectError} />
      </div>
      <Link className="button button--primary" to={analyzePath}>
        {analysis === null ? "Run analysis" : "Upload new version"}
      </Link>
    </header>
  );
}
