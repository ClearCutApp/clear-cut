import { ExternalLink } from "lucide-react";
import type { ReactElement } from "react";

import type { BibleFact, Citation, QuestionAnswer } from "../../api/client";
import { FACT_KIND_LABELS } from "../../theme/labels";

export interface AnswerPanelProps {
  answer: QuestionAnswer;
}

function FactItem({ fact }: { fact: BibleFact }): ReactElement {
  return (
    <li className="ask-answer__fact">
      <span className="ask-answer__kind">{FACT_KIND_LABELS[fact.kind]}</span>
      <p className="ask-answer__fact-text">{fact.text}</p>
      <p className="ask-answer__source">{fact.source}</p>
    </li>
  );
}

/**
 * A legal reference lives outside the app, and the analysis in session
 * would not survive following it in place, so it opens in a new tab.
 */
function ReferenceItem({ citation }: { citation: Citation }): ReactElement {
  return (
    <li className="ask-answer__reference">
      <a
        className="ask-answer__link"
        href={citation.uri}
        target="_blank"
        rel="noreferrer"
      >
        {citation.title}
        <ExternalLink size={14} aria-hidden="true" />
      </a>
      <p className="ask-answer__snippet">{citation.snippet}</p>
    </li>
  );
}

/**
 * A grounded answer: the text, then what it stood on. A cited answer is
 * the product's whole claim (SDD Section 4.2), so an empty fact or
 * reference list is said in words rather than hidden.
 */
export function AnswerPanel({ answer }: AnswerPanelProps): ReactElement {
  return (
    <article className="ask-answer" aria-label="Answer">
      <p className="ask-answer__text">{answer.text}</p>
      <div className="ask-answer__grounding">
        <section className="ask-answer__group">
          <h3>Bible facts</h3>
          {answer.facts.length === 0 ? (
            <p className="ask-answer__none">No bible facts were used.</p>
          ) : (
            <ul className="ask-answer__list">
              {answer.facts.map((fact) => (
                <FactItem key={fact.fact_id} fact={fact} />
              ))}
            </ul>
          )}
        </section>
        <section className="ask-answer__group">
          <h3>Legal references</h3>
          {answer.citations.length === 0 ? (
            <p className="ask-answer__none">No legal references were returned.</p>
          ) : (
            <ul className="ask-answer__list">
              {answer.citations.map((citation, index) => (
                <ReferenceItem key={`${index}:${citation.uri}`} citation={citation} />
              ))}
            </ul>
          )}
        </section>
      </div>
    </article>
  );
}
