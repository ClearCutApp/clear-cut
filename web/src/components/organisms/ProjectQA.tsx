import { useState, type FormEvent, type ReactElement } from "react";

import {
  ApiError,
  postQuestion,
  type QuestionResponse,
} from "../../api/client";

export interface ProjectQAProps {
  projectId: string;
  jurisdictionCode: string;
}

const GENERIC_QUESTION_ERROR = "The question request failed unexpectedly.";

/**
 * A free-text question against the project bible and rights research,
 * answered with grounded text, the facts it drew on, and its citations.
 * A cited answer is the product's whole claim (SDD Section 4.2), so the
 * citation list is not optional decoration.
 */
export function ProjectQA({
  projectId,
  jurisdictionCode,
}: ProjectQAProps): ReactElement {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<QuestionResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const response = await postQuestion(projectId, jurisdictionCode, question);
      setAnswer(response);
    } catch (thrown) {
      setError(thrown instanceof ApiError ? thrown.message : GENERIC_QUESTION_ERROR);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="project-qa">
      <h2>Ask the project</h2>
      <form onSubmit={(event) => void handleSubmit(event)}>
        <div className="field">
          <label htmlFor="project-qa-question">Question</label>
          <textarea
            id="project-qa-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
        </div>
        <button type="submit" className="button button--primary" disabled={submitting}>
          {submitting ? "Asking…" : "Ask"}
        </button>
      </form>

      {error !== null && (
        <p className="error-panel" role="alert">
          {error}
        </p>
      )}

      {answer !== null && (
        <div className="qa-answer">
          <p className="qa-answer__text">{answer.text}</p>
          {answer.facts.length > 0 && (
            <ul className="qa-facts">
              {answer.facts.map((fact) => (
                <li key={fact.fact_id} className="qa-fact">
                  <span className="qa-fact__kind">{fact.kind}</span>
                  <span className="qa-fact__text">
                    {fact.text} ({fact.source})
                  </span>
                </li>
              ))}
            </ul>
          )}
          {answer.citations.length > 0 && (
            <ul className="citation-list">
              {answer.citations.map((citation) => (
                <li key={citation.uri}>
                  <a href={citation.uri}>{citation.title}</a>
                  <p className="citation-snippet">{citation.snippet}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
