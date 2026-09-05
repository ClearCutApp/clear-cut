import { useId, useState, type FormEvent, type ReactElement } from "react";

import type { ScriptCreate } from "../../api/client";
import { ErrorNotice } from "../atoms/ErrorNotice";

export interface AnalyzeFormProps {
  initialGcsUri: string;
  initialJurisdictionCode: string;
  /** The version this upload will be. The caller derives it from the
   * stored versions; the field stays editable for a re-run. */
  initialVersion: number;
  submitting: boolean;
  error: string | null;
  onSubmit: (request: ScriptCreate) => void;
}

/**
 * The three fields `ScriptCreate` has. `gcs_uri` is a text field, never a
 * file picker: the contract uploads a PDF through its own endpoint and
 * hands back the URI, and this form queues the analysis of one that is
 * already stored.
 *
 * The project is not a field. It is the collection in the path, so it comes
 * from the route rather than from something a producer can mistype into a
 * 404.
 *
 * Presentational: it builds the request and calls `onSubmit`, never the
 * client.
 */
export function AnalyzeForm({
  initialGcsUri,
  initialJurisdictionCode,
  initialVersion,
  submitting,
  error,
  onSubmit,
}: AnalyzeFormProps): ReactElement {
  const gcsUriId = useId();
  const jurisdictionId = useId();
  const versionId = useId();
  const [gcsUri, setGcsUri] = useState(initialGcsUri);
  const [jurisdictionCode, setJurisdictionCode] = useState(initialJurisdictionCode);
  const [version, setVersion] = useState(initialVersion);

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onSubmit({
      gcs_uri: gcsUri,
      version,
      jurisdiction_code: jurisdictionCode,
    });
  }

  return (
    <form className="analyze-form" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor={gcsUriId}>Script URI</label>
        <input
          id={gcsUriId}
          type="text"
          required
          className="field__input--mono"
          value={gcsUri}
          disabled={submitting}
          onChange={(event) => setGcsUri(event.target.value)}
        />
      </div>

      <div className="field">
        <label htmlFor={jurisdictionId}>Jurisdiction code</label>
        <input
          id={jurisdictionId}
          type="text"
          required
          value={jurisdictionCode}
          disabled={submitting}
          onChange={(event) => setJurisdictionCode(event.target.value)}
        />
      </div>

      <div className="field">
        <label htmlFor={versionId}>Version</label>
        <input
          id={versionId}
          type="number"
          min={1}
          value={version}
          disabled={submitting}
          onChange={(event) => setVersion(Number(event.target.value))}
        />
      </div>

      <button type="submit" className="button button--primary" disabled={submitting}>
        {submitting ? "Analyzing…" : "Analyze"}
      </button>

      <ErrorNotice message={error} />
    </form>
  );
}
