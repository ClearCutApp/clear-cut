import { useState, type ReactElement } from "react";
import { useNavigate } from "react-router";

import type { ScriptCreate } from "../api/client";
import { AnalyzeForm } from "../components/molecules/AnalyzeForm";
import { ScriptFileUpload } from "../features/analyze/ScriptFileUpload";
import { useProject } from "../state/ProjectContext";
import { useServerMode } from "../state/ServerModeContext";
import { RevisionAnalysisView } from "./RevisionAnalysisView";

/**
 * Where an analysis is started. Queueing answers 202 and the data layer
 * polls the job from there, so this view's whole job is to hand over the
 * request, say plainly that the wait is minutes rather than seconds, and
 * open the result when it lands.
 *
 * The version offered is one past the newest stored version, which is what
 * the delta path needs: version 1 runs the full pipeline, and anything
 * above it re-analyses only the scenes whose content hash changed.
 */
export function AnalyzeView(): ReactElement {
  const mode = useServerMode();
  return mode === "live" ? <RevisionAnalysisView /> : <LegacyAnalyzeView />;
}

function LegacyAnalyzeView(): ReactElement {
  const { projectId, jurisdictionCode, scripts, analysis, analysisError, runAnalysis, uploadScript } =
    useProject();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [storedFileId, setStoredFileId] = useState<string | null>(null);
  const [storedUri, setStoredUri] = useState<string | null>(null);
  const navigate = useNavigate();

  async function handleChoose(file: File): Promise<void> {
    setUploading(true);
    setUploadError(null);
    const outcome = await uploadScript(file);
    setUploading(false);
    if (outcome.ok) {
      setStoredUri(outcome.value.gcs_uri);
      setStoredFileId(outcome.value.file_id ?? null);
      return;
    }
    setUploadError(outcome.message);
  }

  // The form holds its own field state from the moment it mounts, so it
  // waits for the version list rather than opening at 1 and silently
  // disagreeing with the stored versions a second later.
  const versionsKnown = scripts !== null || analysisError !== null;
  const nextVersion = (scripts?.[0]?.version ?? analysis?.version ?? 0) + 1;

  async function handleSubmit(request: ScriptCreate): Promise<void> {
    setSubmitting(true);
    setError(null);
    const outcome = await runAnalysis(
      storedFileId === null ? request : { ...request, file_id: storedFileId },
    );
    setSubmitting(false);
    if (outcome.ok) {
      await navigate(`/projects/${encodeURIComponent(projectId)}`);
      return;
    }
    setError(outcome.message);
  }

  return (
    <section className="analyze">
      <h2>Run analysis</h2>
      <p>
        The script is read by Document AI and assessed scene by scene, which
        takes minutes on a feature. This page waits for the run and opens the
        tracker when it finishes; the run continues on the server whether or
        not this page is still open.
      </p>
      {analysisError !== null && (
        <p>
          The stored versions could not be read, so the version below is not
          derived from them. Check it before queueing a run: a version above 1
          is refused when the server has no previous version to diff against.
        </p>
      )}
      <ScriptFileUpload
        uploading={uploading}
        storedUri={storedUri}
        error={uploadError}
        onChoose={(file) => void handleChoose(file)}
      />

      {versionsKnown ? (
        <AnalyzeForm
          // Remounted when an upload lands, so the URI field opens on the
          // object just stored. The form owns its fields from mount, which
          // is what keeps a producer's edit from being overwritten mid-typing.
          key={storedUri ?? "no-upload"}
          initialGcsUri={storedUri ?? analysis?.gcs_uri ?? ""}
          initialJurisdictionCode={jurisdictionCode}
          initialVersion={nextVersion}
          submitting={submitting}
          error={error}
          onSubmit={(request) => void handleSubmit(request)}
        />
      ) : (
        <p>Reading the versions already stored for this project.</p>
      )}
    </section>
  );
}
