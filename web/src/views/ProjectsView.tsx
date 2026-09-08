import { useMemo, useRef, useState, type ReactElement } from "react";
import { Plus, ArrowRight, FileText, ScanLine, CheckCircle2 } from "lucide-react";
import { useNavigate } from "react-router";

import { useServerMode } from "../state/ServerModeContext";
import { useLocale } from "../state/LocaleContext";
import { WorkspaceOnboarding } from "../features/projects/WorkspaceOnboarding";
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
  const mode = useServerMode();
  const { text } = useLocale();
  const creationRef = useRef<HTMLElement>(null);
  const [organizationId, setOrganizationId] = useState("");

  const rows = useMemo(() => {
    if (projects === null) {
      return [];
    }
    return newestFirst(searchProjects(applyProjectFilter(projects, filter), search));
  }, [projects, filter, search]);

  async function handleCreate(request: ProjectCreate): Promise<void> {
    setCreateError(null);
    const outcome = await create(mode === "live" ? { ...request, organization_id: organizationId } : request);
    if (outcome.ok) {
      await navigate(`/projects/${encodeURIComponent(outcome.value.project_id)}`);
      return;
    }
    setCreateError(outcome.message);
  }

  return (
    <section className="projects">
      <header className="projects__header">
        <div><h1>{text("Projects", "Proyectos")}</h1>
        <p className="projects__subtitle">
          {text("Your assigned projects and production jurisdictions.", "Tus proyectos asignados y jurisdicciones de producción.")}
        </p></div>
        <button className="button button--primary" type="button" onClick={() => { creationRef.current?.focus(); creationRef.current?.scrollIntoView?.({ block: "start" }); }}><Plus size={16} aria-hidden="true" />{text("New project", "Nuevo proyecto")}</button>
      </header>
      <ErrorNotice message={projectsError} />
      {projects === null && projectsError === null && <p>{text("Loading projects…", "Cargando proyectos…")}</p>}
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
            <EmptyState title={text("No projects assigned yet.", "Aún no tienes proyectos asignados.")} />
          ) : (
            <div className="projects__list">
              {rows.length === 0 ? (
                <EmptyState title={text("No project matches the current filter.", "Ningún proyecto coincide con el filtro.")} />
              ) : (
                rows.map((project) => (
                  <ProjectRow key={project.project_id} project={project} />
                ))
              )}
            </div>
          )}
        </>
      )}
      <section className="projects__creation" ref={creationRef} tabIndex={-1} aria-label={text("Create a project", "Crear un proyecto")}>
      <div className="projects__creation-main">
      {mode === "live" && <WorkspaceOnboarding onSelect={setOrganizationId} />}
      {(mode !== "live" || organizationId !== "") && <CreateProjectForm
        jurisdictions={jurisdictions}
        jurisdictionsError={jurisdictionsError}
        submitting={creating}
        error={createError}
        onSubmit={(request) => void handleCreate(request)}
      />}
      </div>
      <aside className="projects__guide">
        <p className="projects__eyebrow">{text("FROM SCRIPT TO SCREEN", "DEL GUION A LA PANTALLA")}</p>
        <h2>{text("Give your next story a workspace.", "Un espacio para tu próxima historia.")}</h2>
        <ol>
          <li><FileText size={20} aria-hidden="true" /><div><strong>{text("Bring your screenplay", "Carga tu guion")}</strong><p>{text("Upload a PDF or DOCX, or write directly in the editor.", "Carga un PDF o DOCX, o escribe directamente en el editor.")}</p></div></li>
          <li><ScanLine size={20} aria-hidden="true" /><div><strong>{text("Review scenes and sources", "Revisa escenas y fuentes")}</strong><p>{text("Examine potential rights issues in the context of your production.", "Examina posibles cuestiones de derechos en el contexto de tu producción.")}</p></div></li>
          <li><CheckCircle2 size={20} aria-hidden="true" /><div><strong>{text("Record your decisions", "Registra tus decisiones")}</strong><p>{text("Keep supporting documents and human clearance decisions together.", "Reúne documentos de respaldo y decisiones de autorización de tu equipo.")}</p></div></li>
        </ol>
        <p className="projects__guide-next">{text("Next: upload your first script", "Siguiente: carga tu primer guion")}<ArrowRight size={16} aria-hidden="true" /></p>
      </aside>
      </section>
    </section>
  );
}
