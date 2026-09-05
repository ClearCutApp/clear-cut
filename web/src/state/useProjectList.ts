import { useCallback, useEffect, useState } from "react";

import {
  createProject,
  listJurisdictions,
  listProjects,
  type Jurisdiction,
  type Project,
  type ProjectCreate,
} from "../api/client";
import { attempt, failureMessage, type Outcome } from "./outcome";

const GENERIC_PROJECTS_ERROR = "The projects request failed unexpectedly.";
const GENERIC_JURISDICTIONS_ERROR = "The jurisdictions request failed unexpectedly.";
const GENERIC_CREATE_ERROR = "Creating the project failed unexpectedly.";

export interface ProjectListState {
  /** Null until the mount GET answers; `[]` when the server holds none. */
  projects: Project[] | null;
  projectsError: string | null;
  /** The codes a new project may be created under. Null until they answer. */
  jurisdictions: Jurisdiction[] | null;
  jurisdictionsError: string | null;
  /** Creates the project and puts it at the head of the list on success. */
  create: (request: ProjectCreate) => Promise<Outcome<Project>>;
  creating: boolean;
}

/**
 * The data layer for the landing view, which is the one screen outside a
 * project and so outside `ProjectProvider`. It keeps the same rule: the
 * view reads state and calls actions, and `client.ts` is called here.
 *
 * The two reads are independent. The list is the screen; the jurisdictions
 * only fill the create form's select, so losing them leaves the projects on
 * screen and takes the form's options away rather than the whole page.
 */
export function useProjectList(): ProjectListState {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [projectsError, setProjectsError] = useState<string | null>(null);
  const [jurisdictions, setJurisdictions] = useState<Jurisdiction[] | null>(null);
  const [jurisdictionsError, setJurisdictionsError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listProjects()
      .then((found) => {
        if (!cancelled) {
          setProjects(found);
          setProjectsError(null);
        }
      })
      .catch((thrown: unknown) => {
        if (!cancelled) {
          setProjectsError(failureMessage(thrown, GENERIC_PROJECTS_ERROR));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    listJurisdictions()
      .then((found) => {
        if (!cancelled) {
          setJurisdictions(found);
          setJurisdictionsError(null);
        }
      })
      .catch((thrown: unknown) => {
        if (!cancelled) {
          setJurisdictionsError(failureMessage(thrown, GENERIC_JURISDICTIONS_ERROR));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const create = useCallback(
    async (request: ProjectCreate): Promise<Outcome<Project>> => {
      setCreating(true);
      try {
        const outcome = await attempt(() => createProject(request), GENERIC_CREATE_ERROR);
        if (outcome.ok) {
          // The 201 body is the project as stored, so the new row is the
          // server's own answer rather than a re-read or an echo of the form.
          setProjects((current) => [outcome.value, ...(current ?? [])]);
        }
        return outcome;
      } finally {
        setCreating(false);
      }
    },
    [],
  );

  return {
    projects,
    projectsError,
    jurisdictions,
    jurisdictionsError,
    create,
    creating,
  };
}
