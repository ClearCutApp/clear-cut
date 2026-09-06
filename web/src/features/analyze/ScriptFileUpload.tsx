import { useId, useState, type ChangeEvent, type ReactElement } from "react";

import { ErrorNotice } from "../../components/atoms/ErrorNotice";

/** The contract refuses anything larger (`413`), so the browser says so
 * before spending a producer's upload on a rejection. */
const MAX_BYTES = 25 * 1024 * 1024;

export interface ScriptFileUploadProps {
  uploading: boolean;
  /** The URI a completed upload returned, or null before one has. */
  storedUri: string | null;
  error: string | null;
  onChoose: (file: File) => void;
}

export function describeSize(bytes: number): string {
  const mib = bytes / (1024 * 1024);
  return mib >= 1 ? `${mib.toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** The reason a chosen file cannot be sent, or null when it can.
 *
 * Both checks exist server-side too and this does not replace them. It
 * spends the producer's time better: a 60 MB screenplay refused after the
 * transfer is the same answer, minutes later.
 */
export function rejectionFor(file: File): string | null {
  const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  if (!isPdf) {
    return "ClearCut reads screenplays through Document AI, which is configured for PDF alone.";
  }
  if (file.size > MAX_BYTES) {
    return `That file is ${describeSize(file.size)}. The limit is 25 MB.`;
  }
  return null;
}

/**
 * Chooses a screenplay and hands the file up. Presentational: the upload
 * itself belongs to the view, which owns every call to the client.
 *
 * Upload and analysis stay two steps, as the contract has them. The URI is
 * shown after a successful upload rather than hidden, because the field it
 * fills is still editable and a producer re-running an old version needs to
 * see which object they are about to analyse.
 */
export function ScriptFileUpload({
  uploading,
  storedUri,
  error,
  onChoose,
}: ScriptFileUploadProps): ReactElement {
  const inputId = useId();
  const [rejected, setRejected] = useState<string | null>(null);

  function handleChange(event: ChangeEvent<HTMLInputElement>): void {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const rejection = rejectionFor(file);
    setRejected(rejection);
    if (rejection === null) {
      onChoose(file);
    }
  }

  return (
    <div className="script-upload">
      <div className="field">
        <label htmlFor={inputId}>Screenplay PDF</label>
        <input
          id={inputId}
          type="file"
          accept="application/pdf,.pdf"
          disabled={uploading}
          onChange={handleChange}
        />
        <p className="script-upload__hint">
          PDF, up to 25 MB. The file is stored first and analysed second, so
          re-running a version costs no second upload.
        </p>
      </div>

      {uploading && <p className="script-upload__status">Storing the screenplay…</p>}

      {storedUri !== null && !uploading && (
        <p className="script-upload__stored">
          Stored as <code className="script-upload__uri">{storedUri}</code>
        </p>
      )}

      <ErrorNotice message={rejected ?? error} />
    </div>
  );
}
