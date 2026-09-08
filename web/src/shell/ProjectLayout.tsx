import type { ReactElement } from "react";
import { NavLink, Outlet, useParams } from "react-router";

import { ItemDetailPanelHost } from "../features/item/ItemDetailPanelHost";
import { ProjectProvider, useProject } from "../state/ProjectContext";
import { useLocale } from "../state/LocaleContext";
import { ProjectHeader } from "./ProjectHeader";
import { RevisionStatus } from "../features/analysis/RevisionStatus";

/**
 * Mounts the project's data layer for the routes under `/projects/:id`
 * and frames them: header, the routed view, and the item detail panel.
 * The provider is keyed by project id so moving between projects starts
 * from a clean slate rather than showing one project's rows under
 * another's header.
 */
export function ProjectLayout(): ReactElement {
  const { projectId = "" } = useParams();
  return (
    <ProjectProvider key={projectId} projectId={projectId}>
      <ProjectFrame />
    </ProjectProvider>
  );
}

function ProjectFrame(): ReactElement {
  const { selectedItemId, projectId } = useProject();
  const { text } = useLocale();
  const root = `/projects/${encodeURIComponent(projectId)}`;
  const className =
    selectedItemId === null
      ? "project-layout"
      : "project-layout project-layout--panel-open";
  return (
    <div className={className}>
      <div className="project-layout__content">
        <ProjectHeader />
        <RevisionStatus />
        <Outlet />
      </div>
      <ItemDetailPanelHost />
      <nav className="mobile-project-nav" aria-label={text("Project tools", "Herramientas del proyecto")}><NavLink to={`${root}/ask`}>{text("Ask", "Preguntar")}</NavLink><NavLink to={`${root}/editor`}>{text("Script", "Guion")}</NavLink><NavLink to={`${root}/clearances`}>{text("Clearances", "Autorizaciones")}</NavLink></nav>
    </div>
  );
}
