import { ExternalLink } from "lucide-react";
import { useId, type ReactElement } from "react";

import type { Citation, Finding } from "../../api/client";
import { CATEGORY_LABELS, NER_LABELS } from "../../theme/labels";

export interface FindingFactsProps {
  finding: Finding;
  jurisdictionName: string;
}

function CitationList({ citations }: { citations: Citation[] }): ReactElement {
  if (citations.length === 0) {
    return <p className="item-facts__meta">No legal references were returned.</p>;
  }
  return (
    <ul className="item-citations">
      {citations.map((citation) => (
        <li key={citation.uri} className="item-citations__item">
          <a
            className="item-citations__link"
            href={citation.uri}
            target="_blank"
            rel="noreferrer"
          >
            {citation.title}
            <ExternalLink aria-hidden="true" size={12} />
          </a>
          <p className="item-citations__snippet">{citation.snippet}</p>
        </li>
      ))}
    </ul>
  );
}

/**
 * What the analysis said about the finding, as words: the flagged text,
 * the category and entity labels from the theme, the risk word, the
 * document it calls for, the bible fact it contradicts when it is a
 * continuity finding, and the territory it was assessed under. The entity
 * row is omitted rather than blanked when the server sent no label. The
 * legal references are the citations the analysis returned, or an honest
 * sentence when it returned none; there is no explanation or usage prose
 * to show because the API carries none (Missing API registry).
 */
export function FindingFacts({ finding, jurisdictionName }: FindingFactsProps): ReactElement {
  const titleId = useId();
  return (
    <section className="item-facts" aria-labelledby={titleId}>
      <h3 id={titleId} className="item-facts__title">
        Finding
      </h3>
      <dl className="item-facts__list">
        <div className="item-facts__row">
          <dt>Flagged text</dt>
          <dd>{finding.raw_text}</dd>
        </div>
        <div className="item-facts__row">
          <dt>Category</dt>
          <dd>{CATEGORY_LABELS[finding.category]}</dd>
        </div>
        {finding.ner_label !== null && (
          <div className="item-facts__row">
            <dt>Entity</dt>
            <dd>{NER_LABELS[finding.ner_label]}</dd>
          </div>
        )}
        <div className="item-facts__row">
          <dt>Risk</dt>
          <dd>{finding.risk_level}</dd>
        </div>
        <div className="item-facts__row">
          <dt>Required document</dt>
          <dd>{finding.required_document}</dd>
        </div>
        {finding.contradicts !== null && (
          <div className="item-facts__row">
            <dt>Conflict</dt>
            <dd>Contradicts {finding.contradicts}</dd>
          </div>
        )}
        <div className="item-facts__row">
          <dt>Territory</dt>
          <dd>{jurisdictionName}</dd>
        </div>
      </dl>
      <h3 className="item-facts__title">Legal references</h3>
      <CitationList citations={finding.citations} />
    </section>
  );
}
