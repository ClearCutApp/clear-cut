import { useState, type ReactElement } from "react";

import type { QuestionResponse } from "../api/client";
import { AnswerPanel } from "../features/ask/AnswerPanel";
import { EXAMPLE_QUESTIONS } from "../features/ask/model";
import { QuestionForm } from "../features/ask/QuestionForm";
import { useProject } from "../state/ProjectContext";
import { jurisdictionName } from "../theme/jurisdictions";

/**
 * Questions against the project bible and the jurisdiction's legal corpus.
 * The view holds the one answer on screen and the request state; the data
 * layer sends the question under the project's current jurisdiction. A
 * question that fails leaves the last answer standing with the failure in
 * view, so nothing the reader was looking at disappears.
 */
export function AskView(): ReactElement {
  const { ask, jurisdictionCode } = useProject();
  const [answer, setAnswer] = useState<QuestionResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAsk(question: string): Promise<void> {
    setSubmitting(true);
    setError(null);
    const outcome = await ask(question);
    if (outcome.ok) {
      setAnswer(outcome.value);
    } else {
      setError(outcome.message);
    }
    setSubmitting(false);
  }

  return (
    <section className="ask">
      <header className="ask__intro">
        <h2>Ask ClearCut</h2>
        <p className="ask__lede">
          Answers are grounded in this project's bible facts and the legal
          corpus for {jurisdictionName(jurisdictionCode)}.
        </p>
      </header>
      <QuestionForm
        examples={EXAMPLE_QUESTIONS}
        submitting={submitting}
        error={error}
        onAsk={(question) => void handleAsk(question)}
      />
      {answer !== null && <AnswerPanel answer={answer} />}
    </section>
  );
}
