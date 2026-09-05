import { render, type RenderResult } from "@testing-library/react";
import { useEffect, type ReactElement } from "react";
import { MemoryRouter, useLocation } from "react-router";

import type { Script } from "../api/client";
import { ProjectProvider, useProject } from "../state/ProjectContext";

export interface RenderWithProjectOptions {
  /** Defaults to a neutral id; tests that need the demo project pass it. */
  projectId?: string;
  /** The router's starting location; defaults to the project's overview. */
  path?: string;
  /** A script already loaded, as if the mount GET had answered. */
  analysis?: Script | null;
  /** An item already selected, as if a row had been opened. */
  selectedItemId?: string | null;
}

function Preselect({ itemId }: { itemId: string }): null {
  const { selectItem } = useProject();
  useEffect(() => {
    selectItem(itemId);
  }, [itemId, selectItem]);
  return null;
}

/** Renders the router's current path so a test can assert a navigation. */
function LocationProbe(): ReactElement {
  const location = useLocation();
  return (
    <span hidden data-testid="location">
      {location.pathname}
    </span>
  );
}

/**
 * Mounts `ui` the way a project view is mounted in the app: under a
 * MemoryRouter and a ProjectProvider. Stub `fetch` first with `stubFetch`;
 * the provider's mount GET runs immediately. Navigate with absolute paths
 * built from `projectId`, which is what the views do, and read the result
 * from the `location` test id.
 */
export function renderWithProject(
  ui: ReactElement,
  options: RenderWithProjectOptions = {},
): RenderResult {
  const {
    projectId = "proj_1",
    path = `/projects/${encodeURIComponent(projectId)}`,
    analysis = null,
    selectedItemId = null,
  } = options;
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ProjectProvider projectId={projectId} initialAnalysis={analysis}>
        {selectedItemId !== null && <Preselect itemId={selectedItemId} />}
        {ui}
        <LocationProbe />
      </ProjectProvider>
    </MemoryRouter>,
  );
}
