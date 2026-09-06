import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import type { ReactElement } from "react";

import type { TrackerState } from "../../api/client";
import { RiskBadge } from "../../components/atoms/RiskBadge";
import { CATEGORY_LABELS, NER_LABELS } from "../../theme/labels";
import type { Suggestion } from "./model";

export interface SuggestionCardProps {
  suggestion: Suggestion;
  expanded: boolean;
  selected: boolean;
  onToggle: () => void;
}

const STATE_WORDS: Record<TrackerState, string> = {
  BLOCKED: "Blocked",
  IN_PROGRESS: "In progress",
  CLEARED: "Cleared",
};

/**
 * One finding in the rail. Collapsed it carries what a reader picks a row
 * by: the flagged text, its risk, and where in the script it sits. Opened
 * it carries the rest of the analysis's facts.
 *
 * A finding the paper marks nowhere says so here, with its scene and page,
 * because it is the only place a reader will meet it: the analysis
 * reported a paraphrase of the line rather than a stretch of it, and a
 * position was never computed for it.
 */
export function SuggestionCard({
  suggestion,
  expanded,
  selected,
  onToggle,
}: SuggestionCardProps): ReactElement {
  const { finding, state, needsReview, hasSpan } = suggestion;
  const classes = ["suggestion"];
  if (selected) {
    classes.push("suggestion--selected");
  }
  const bodyId = `suggestion-body-${finding.finding_id}`;
  return (
    <li className={classes.join(" ")}>
      <button
        type="button"
        className="suggestion__summary"
        aria-expanded={expanded}
        aria-controls={bodyId}
        onClick={onToggle}
      >
        <span className="suggestion__chevron" aria-hidden="true">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
        <span className="suggestion__text">{finding.raw_text}</span>
        <RiskBadge risk={finding.risk_level} />
      </button>
      <p className="suggestion__where">
        Scene {finding.scene_number}, page {finding.page}
        {state !== null && ` · ${STATE_WORDS[state]}`}
        {needsReview && " · Needs review"}
      </p>
      {!hasSpan && (
        <p className="suggestion__unmarked">
          The analysis reported this as a paraphrase of the line, not a stretch of it, so it is
          marked nowhere on the page.
        </p>
      )}
      <div className="suggestion__body" id={bodyId} hidden={!expanded}>
        <dl className="suggestion__facts">
          <div className="suggestion__fact">
            <dt>Category</dt>
            <dd>{CATEGORY_LABELS[finding.category]}</dd>
          </div>
          {finding.ner_label !== null && (
            <div className="suggestion__fact">
              <dt>Entity</dt>
              <dd>{NER_LABELS[finding.ner_label]}</dd>
            </div>
          )}
          <div className="suggestion__fact">
            <dt>Required document</dt>
            <dd>{finding.required_document}</dd>
          </div>
          {finding.contradicts !== null && (
            <div className="suggestion__fact">
              <dt>Conflict</dt>
              <dd>Contradicts {finding.contradicts}</dd>
            </div>
          )}
        </dl>
        {finding.citations.length === 0 ? (
          <p className="suggestion__none">No legal references were returned.</p>
        ) : (
          <ul className="suggestion__citations">
            {finding.citations.map((citation) => (
              <li key={citation.uri}>
                <a
                  className="suggestion__link"
                  href={citation.uri}
                  target="_blank"
                  rel="noreferrer"
                >
                  {citation.title}
                  <ExternalLink size={12} aria-hidden="true" />
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </li>
  );
}
