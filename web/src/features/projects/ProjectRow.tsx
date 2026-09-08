import { ArrowRight } from "lucide-react";
import type { ReactElement } from "react";
import { Link } from "react-router";

import { useLocale } from "../../state/LocaleContext";
import type { Project } from "../../api/client";
import { jurisdictionName } from "../../theme/jurisdictions";

export interface ProjectRowProps {
  project: Project;
}



/** The reader's locale; an unparseable stamp is shown verbatim rather than
 * as "Invalid Date". */
function formatCreatedAt(iso: string, locale: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(date);
}

/**
 * One project as the API describes it: title, id, jurisdiction and when it
 * was created, with the way in.
 *
 * The design's poster art, team avatars, format badge, clearance progress
 * bar and "updated 2h ago" are absent from `Project` and from every other
 * response, so the row is narrower than the design and says nothing it
 * cannot source. A row with no poster reads as a row with no poster; a
 * poster invented for it would read as this project's poster.
 */
export function ProjectRow({ project }: ProjectRowProps): ReactElement {
  const { text, locale } = useLocale();
  const path = `/projects/${encodeURIComponent(project.project_id)}`;
  return (
    <article className="project-row">
      <div className="project-row__identity">
        <h3 className="project-row__title">{project.title}</h3>
        <p className="project-row__id">{project.project_id}</p>
      </div>
      <dl className="project-row__facts">
        <div className="project-row__fact">
          <dt>{text("Jurisdiction", "Jurisdicción")}</dt>
          <dd>{jurisdictionName(project.jurisdiction_code, locale)}</dd>
        </div>
        <div className="project-row__fact">
          <dt>{text("Created", "Creado")}</dt>
          <dd>
            <time dateTime={project.created_at}>{formatCreatedAt(project.created_at, locale)}</time>
          </dd>
        </div>
      </dl>
      <Link className="project-row__open" to={path}>
        {text("Open", "Abrir")} {project.title}
        <ArrowRight aria-hidden="true" size={14} />
      </Link>
    </article>
  );
}
