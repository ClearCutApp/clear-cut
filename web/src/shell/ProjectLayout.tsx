import type { ReactElement } from "react";
import { Outlet, useParams } from "react-router";

import { ItemDetailPanelHost } from "../features/item/ItemDetailPanelHost";
import { ProjectProvider, useProject } from "../state/ProjectContext";
import { ProjectHeader } from "./ProjectHeader";

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
  const { selectedItemId } = useProject();
  const className =
    selectedItemId === null
      ? "project-layout"
      : "project-layout project-layout--panel-open";
  return (
    <div className={className}>
      <div className="project-layout__content">
        <ProjectHeader />
        <Outlet />
      </div>
      <ItemDetailPanelHost />
    </div>
  );
}
