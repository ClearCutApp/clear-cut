import { useState, type FormEvent, type ReactElement } from "react";

import { ErrorNotice } from "../../components/atoms/ErrorNotice";
import { isAskable } from "./model";

export interface QuestionFormProps {
  examples: readonly string[];
  submitting: boolean;
  error: string | null;
  onAsk: (question: string) => void;
}

const QUESTION_ID = "ask-question";

/**
 * A free-text question with example chips that fill it in. The form owns
 * the draft only; the request, its answer and its failure belong to the
 * view, which hands them back as `submitting` and `error`. There is no
 * microphone and no web-search switch: the questions endpoint takes text
 * and answers from the corpus it has (SDD Section 4, MISSING rows).
 */
export function QuestionForm({
  examples,
  submitting,
  error,
  onAsk,
}: QuestionFormProps): ReactElement {
  const [question, setQuestion] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!isAskable(question)) {
      return;
    }
    onAsk(question.trim());
  }

  return (
    <form className="ask-form" onSubmit={handleSubmit}>
      <ul className="ask-form__examples" aria-label="Example questions">
        {examples.map((example) => (
          <li key={example}>
            <button
              type="button"
              className="ask-form__example"
              onClick={() => setQuestion(example)}
            >
              {example}
            </button>
          </li>
        ))}
      </ul>
      <div className="field">
        <label htmlFor={QUESTION_ID}>Question</label>
        <textarea
          id={QUESTION_ID}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
        />
      </div>
      <div>
        <button type="submit" className="button button--primary" disabled={submitting}>
          {submitting ? "Asking…" : "Ask"}
        </button>
      </div>
      <ErrorNotice message={error} />
    </form>
  );
}
