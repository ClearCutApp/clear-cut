import type { ReactElement } from "react";

import type { Finding, Scene } from "../../api/client";
import { RiskBadge } from "../atoms/RiskBadge";

export interface SceneCardProps {
  scene: Scene;
  findings: Finding[];
}

/**
 * One scene from an `AnalyzeResponse`, with the findings extracted from it.
 * Presentational only -- receives `scene` and `findings` as props, never
 * fetches. `contradicts` is the continuity finding's carried fact id
 * (SDD Section 8(d)); rendered only when non-null.
 */
export function SceneCard({ scene, findings }: SceneCardProps): ReactElement {
  return (
    <article className="scene-card">
      <h3>{scene.heading}</h3>
      <p className="scene-pages">
        Pages {scene.page_start}–{scene.page_end}
      </p>
      {findings.length === 0 ? (
        <p className="empty-state">No findings in this scene.</p>
      ) : (
        <ul className="finding-list">
          {findings.map((finding) => (
            <li key={finding.finding_id} className="finding">
              <div className="finding__header">
                <RiskBadge risk={finding.risk_level} />
                <span className="finding-category">{finding.category}</span>
              </div>
              <p>Required document: {finding.required_document}</p>
              {finding.contradicts !== null && (
                <p className="contradicts">
                  Contradicts fact {finding.contradicts}
                </p>
              )}
              {finding.citations.length > 0 && (
                <ul className="citation-list">
                  {finding.citations.map((citation) => (
                    <li key={citation.uri}>
                      <a href={citation.uri}>{citation.title}</a>
                      <p className="citation-snippet">{citation.snippet}</p>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
