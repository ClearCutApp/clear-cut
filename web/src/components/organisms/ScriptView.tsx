import { useState, type ReactElement } from "react";

import {
  ApiError,
  postAnalyze,
  type AnalyzeRequest,
  type AnalyzeResponse,
} from "../../api/client";
import { AnalyzeForm } from "../molecules/AnalyzeForm";
import { SceneCard } from "../molecules/SceneCard";

export interface ScriptViewProps {
  analysis: AnalyzeResponse | null;
  onAnalyzed: (response: AnalyzeResponse) => void;
  projectId: string;
  gcsUri: string;
  jurisdictionCode: string;
  version: number;
}

const GENERIC_ANALYZE_ERROR = "The analyze request failed unexpectedly.";

/**
 * Container for the analyze surface: composes `AnalyzeForm` (presentational)
 * and one `SceneCard` per scene, keyed to that scene's findings. Owns the
 * `postAnalyze` call and its submitting/error state; `App` owns the
 * resulting `analysis` itself so the tracker can react to it too.
 */
export function ScriptView({
  analysis,
  onAnalyzed,
  projectId,
  gcsUri,
  jurisdictionCode,
  version,
}: ScriptViewProps): ReactElement {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(request: AnalyzeRequest): Promise<void> {
    setSubmitting(true);
    setError(null);
    try {
      const response = await postAnalyze(request);
      onAnalyzed(response);
    } catch (thrown) {
      setError(thrown instanceof ApiError ? thrown.message : GENERIC_ANALYZE_ERROR);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="script-view">
      <h2>Script analysis</h2>
      <AnalyzeForm
        initialProjectId={projectId}
        initialGcsUri={gcsUri}
        initialJurisdictionCode={jurisdictionCode}
        initialVersion={version}
        submitting={submitting}
        error={error}
        onSubmit={handleSubmit}
      />
      {analysis !== null && (
        <div className="scene-list">
          {analysis.scenes.map((scene) => (
            <SceneCard
              key={scene.number}
              scene={scene}
              findings={analysis.findings.filter(
                (finding) => finding.scene_number === scene.number,
              )}
            />
          ))}
        </div>
      )}
    </section>
  );
}
