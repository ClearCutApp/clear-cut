import { useId, useState, type FormEvent, type ReactElement } from "react";

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
  const titleId = useId();
  const jurisdictionId = useId();
  const [title, setTitle] = useState("");
  const [jurisdictionCode, setJurisdictionCode] = useState("");

  const options = jurisdictions ?? [];
  const ready = options.length > 0;

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onSubmit({ title, jurisdiction_code: jurisdictionCode });
  }

  return (
    <form className="create-project" onSubmit={handleSubmit}>
      <h2>New project</h2>
      <div className="field">
        <label htmlFor={titleId}>Title</label>
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
        <label htmlFor={jurisdictionId}>Jurisdiction</label>
        <select
          id={jurisdictionId}
          required
          value={jurisdictionCode}
          disabled={submitting || !ready}
          onChange={(event) => setJurisdictionCode(event.target.value)}
        >
          <option value="">Choose a jurisdiction</option>
          {options.map((jurisdiction) => (
            <option key={jurisdiction.code} value={jurisdiction.code}>
              {jurisdiction.display_name}
            </option>
          ))}
        </select>
      </div>
      {!ready && jurisdictionsError === null && (
        <p className="create-project__note">Reading the jurisdictions this server accepts.</p>
      )}
      {jurisdictionsError !== null && (
        <p className="create-project__note">
          The jurisdictions could not be read, and a project cannot be created
          without one. No code is guessed here.
        </p>
      )}
      <ErrorNotice message={jurisdictionsError} />
      <button type="submit" className="button button--primary" disabled={submitting || !ready}>
        {submitting ? "Creating…" : "Create project"}
      </button>
      <ErrorNotice message={error} />
    </form>
  );
}
