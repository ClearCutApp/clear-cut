import { useId, useState, type FormEvent, type ReactElement } from "react";

import { useLocale } from "../../state/LocaleContext";
import { jurisdictionName, LAUNCH_COUNTRIES } from "../../theme/jurisdictions";
import type { Jurisdiction, ProjectCreate } from "../../api/client";
import { ErrorNotice } from "../../components/atoms/ErrorNotice";

export interface CreateProjectFormProps {
  /** Null until the jurisdictions answer; the select has nothing to offer
   * until they do, so the form waits rather than guessing a code. */
  jurisdictions: Jurisdiction[] | null;
  jurisdictionsError: string | null;
  submitting: boolean;
  error: string | null;
  onSubmit: (request: ProjectCreate) => void;
}

/**
 * The two fields `ProjectCreate` has, and no more. The design's project
 * type, other territories, project stage, script notes and attachments are
 * not in the request body, so a producer filling them in would be filling
 * in fields the server discards.
 *
 * Presentational: it builds the request and calls `onSubmit`. The
 * jurisdiction select is driven by the codes the API returns rather than by
 * a list held here, so a code this build has never heard of is still
 * offered.
 */
export function CreateProjectForm({
  jurisdictions,
  jurisdictionsError,
  submitting,
  error,
  onSubmit,
}: CreateProjectFormProps): ReactElement {
  const { text, locale } = useLocale();
  const titleId = useId();
  const jurisdictionId = useId();
  const [title, setTitle] = useState("");
  const [jurisdictionCode, setJurisdictionCode] = useState("");

  const options = (jurisdictions ?? []).filter(jurisdiction => (LAUNCH_COUNTRIES as readonly string[]).includes(jurisdiction.code));
  const ready = options.length > 0;

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onSubmit({ title, jurisdiction_code: jurisdictionCode });
  }

  return (
    <form className="create-project" onSubmit={handleSubmit}>
      <h2>{text("New project", "Nuevo proyecto")}</h2>
      <p className="create-project__note">{text("Set the title and primary production jurisdiction. Add your screenplay next.", "Define el título y la jurisdicción principal de producción. Luego agrega tu guion.")}</p>
      <div className="field">
        <label htmlFor={titleId}>{text("Title", "Título")}</label>
        <input
          id={titleId}
          type="text"
          required
          value={title}
          disabled={submitting}
          onChange={(event) => setTitle(event.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor={jurisdictionId}>{text("Jurisdiction", "Jurisdicción")}</label>
        <select
          id={jurisdictionId}
          required
          value={jurisdictionCode}
          disabled={submitting || !ready}
          onChange={(event) => setJurisdictionCode(event.target.value)}
        >
          <option value="">{text("Choose a jurisdiction", "Elige una jurisdicción")}</option>
          {options.map((jurisdiction) => (
            <option key={jurisdiction.code} value={jurisdiction.code}>
              {locale === "es" ? jurisdictionName(jurisdiction.code, locale) : jurisdiction.display_name}
            </option>
          ))}
        </select>
      </div>
      {!ready && jurisdictionsError === null && (
        <p className="create-project__note">{text("Loading jurisdictions…", "Cargando jurisdicciones…")}</p>
      )}
      {jurisdictionsError !== null && (
        <p className="create-project__note">
          {text("Jurisdictions could not be loaded. Reload to try again.", "No se pudieron cargar las jurisdicciones. Recarga para intentarlo de nuevo.")}
        </p>
      )}
      <ErrorNotice message={jurisdictionsError} />
      <button type="submit" className="button button--primary" disabled={submitting || !ready}>
        {submitting ? text("Creating…", "Creando…") : text("Create project", "Crear proyecto")}
      </button>
      <ErrorNotice message={error} />
    </form>
  );
}
