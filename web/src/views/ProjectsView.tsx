import { useMemo, useState, type ReactElement } from "react";
import { useNavigate } from "react-router";

import type { ProjectCreate } from "../api/client";
import { EmptyState } from "../components/atoms/EmptyState";
import { ErrorNotice } from "../components/atoms/ErrorNotice";
import { CreateProjectForm } from "../features/projects/CreateProjectForm";
import {
  applyProjectFilter,
  newestFirst,
  projectMetrics,
  projectTabs,
  searchProjects,
  type ProjectFilterValue,
} from "../features/projects/model";
import { ProjectFilters } from "../features/projects/ProjectFilters";
import { ProjectMetrics } from "../features/projects/ProjectMetrics";
import { ProjectRow } from "../features/projects/ProjectRow";
import { useProjectList } from "../state/useProjectList";

/**
 * The landing view: the projects this server holds, the numbers they add up
 * to, the jurisdiction tabs and search that narrow them, and the form that
 * creates one. Filter and search live here because they narrow what is
 * rendered, not what the data layer holds.
 *
 * A created project is opened straight away: the producer's next act is
 * always to upload a script to it.
 */
export function ProjectsView(): ReactElement {
  const { projects, projectsError, jurisdictions, jurisdictionsError, create, creating } =
    useProjectList();
  const [filter, setFilter] = useState<ProjectFilterValue>("ALL");
  const [search, setSearch] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const navigate = useNavigate();

  const rows = useMemo(() => {
    if (projects === null) {
      return [];
    }
    return newestFirst(searchProjects(applyProjectFilter(projects, filter), search));
  }, [projects, filter, search]);

  async function handleCreate(request: ProjectCreate): Promise<void> {
    setCreateError(null);
    const outcome = await create(request);
    if (outcome.ok) {
      await navigate(`/projects/${encodeURIComponent(outcome.value.project_id)}`);
      return;
    }
    setCreateError(outcome.message);
  }

  return (
    <section className="projects">
      <header className="projects__header">
        <h1>Projects</h1>
        <p className="projects__subtitle">
          Every project on this server, and the jurisdiction each is cleared
          against.
        </p>
      </header>
      <ErrorNotice message={projectsError} />
      {projects === null && projectsError === null && <p>Loading the projects.</p>}
      {projects !== null && (
        <>
          <ProjectMetrics metrics={projectMetrics(projects)} />
          <ProjectFilters
            tabs={projectTabs(projects)}
            filter={filter}
            onFilterChange={setFilter}
            search={search}
            onSearchChange={setSearch}
          />
          {projects.length === 0 ? (
            <EmptyState title="This server holds no projects yet." />
          ) : (
            <div className="projects__list">
              {rows.length === 0 ? (
                <EmptyState title="No project matches the current filter." />
              ) : (
                rows.map((project) => (
                  <ProjectRow key={project.project_id} project={project} />
                ))
              )}
            </div>
          )}
        </>
      )}
      <CreateProjectForm
        jurisdictions={jurisdictions}
        jurisdictionsError={jurisdictionsError}
        submitting={creating}
        error={createError}
        onSubmit={(request) => void handleCreate(request)}
      />
    </section>
  );
}
