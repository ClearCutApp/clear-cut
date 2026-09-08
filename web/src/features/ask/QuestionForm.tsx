import { useRef, useState, type FormEvent, type ReactElement } from "react";

import { ErrorNotice } from "../../components/atoms/ErrorNotice";
import { VoiceQuestion } from "../voice/VoiceQuestion";
import { useLocale } from "../../state/LocaleContext";
import { isAskable } from "./model";

export interface QuestionFormProps {
  projectId?: string;
  context?: string;
  examples: readonly string[];
  submitting: boolean;
  error: string | null;
  onAsk: (question: string) => void;
}

const QUESTION_ID = "ask-question";

/** Text and reviewed transcription share one draft; submission stays explicit. */
export function QuestionForm({
  projectId,
  context = "",
  examples,
  submitting,
  error,
  onAsk,
}: QuestionFormProps): ReactElement {
  const { text } = useLocale();
  const input = useRef<HTMLTextAreaElement>(null);
  const [transcribed, setTranscribed] = useState(false);
  const [question, setQuestion] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (submitting || !isAskable(question)) {
      return;
    }
    onAsk(question.trim());
  }

  return (
    <form className="ask-form" onSubmit={handleSubmit}>
      {projectId && <VoiceQuestion key={projectId} projectId={projectId} context={context} onTranscript={value => { setQuestion(current => current.trim() ? `${current}\n${value}` : value); setTranscribed(true); input.current?.focus(); }} />}
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
        <label htmlFor={QUESTION_ID}>{text("Question", "Pregunta")}</label>
        {transcribed && <p role="status">{text("Review and edit your transcript before asking.", "Revisa y edita la transcripción antes de preguntar.")}</p>}
        <textarea
          ref={input}
          id={QUESTION_ID}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
        />
      </div>
      <div>
        <button type="submit" className="button button--primary" disabled={submitting}>
          {submitting ? text("Asking…", "Preguntando…") : text("Ask", "Preguntar")}
        </button>
      </div>
      <ErrorNotice message={error} />
    </form>
  );
}
