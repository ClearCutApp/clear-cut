import { useState, type FormEvent, type ReactElement } from "react";

import type { AnalyzeRequest } from "../../api/client";

export interface AnalyzeFormProps {
  initialProjectId: string;
  initialGcsUri: string;
  initialJurisdictionCode: string;
  initialVersion: number;
  submitting: boolean;
  error: string | null;
  onSubmit: (request: AnalyzeRequest) => void;
}

/**
 * The analyze request as four editable text fields, prefilled with the demo
 * values `App` passes down. `gcs_uri` is a text field, never a file picker
 * -- D10 removed multipart upload and the `ScriptStorage` port with it, so
 * the operator runs `gcloud storage cp` first. Presentational: it builds
 * the request and calls `onSubmit`, but never calls `postAnalyze` itself --
 * that is `ScriptView`'s job as the container.
 */
export function AnalyzeForm({
  initialProjectId,
  initialGcsUri,
  initialJurisdictionCode,
  initialVersion,
  submitting,
  error,
  onSubmit,
}: AnalyzeFormProps): ReactElement {
  const [projectId, setProjectId] = useState(initialProjectId);
  const [gcsUri, setGcsUri] = useState(initialGcsUri);
  const [jurisdictionCode, setJurisdictionCode] = useState(
    initialJurisdictionCode,
  );
  const [version, setVersion] = useState(initialVersion);

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    // `project_id` is not a body field since the REST rename; `ScriptView`
    // passes it to `postAnalyze` as the collection being written to.
    onSubmit({
      gcs_uri: gcsUri,
      version,
      jurisdiction_code: jurisdictionCode,
    });
  }

  return (
    <form className="analyze-form" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="analyze-project-id">Project id</label>
        <input
          id="analyze-project-id"
          type="text"
          value={projectId}
          onChange={(event) => setProjectId(event.target.value)}
        />
      </div>

      <div className="field">
        <label htmlFor="analyze-gcs-uri">GCS uri</label>
        <input
          id="analyze-gcs-uri"
          type="text"
          className="field__input--mono"
          value={gcsUri}
          onChange={(event) => setGcsUri(event.target.value)}
        />
      </div>

      <div className="field">
        <label htmlFor="analyze-jurisdiction">Jurisdiction code</label>
        <input
          id="analyze-jurisdiction"
          type="text"
          value={jurisdictionCode}
          onChange={(event) => setJurisdictionCode(event.target.value)}
        />
      </div>

      <div className="field">
        <label htmlFor="analyze-version">Version</label>
        <input
          id="analyze-version"
          type="number"
          value={version}
          onChange={(event) => setVersion(Number(event.target.value))}
        />
      </div>

      <button type="submit" className="button button--primary" disabled={submitting}>
        {submitting ? "Analyzing…" : "Analyze"}
      </button>

      {error !== null && (
        <p className="error-panel" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
