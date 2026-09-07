import { useEffect, useRef, useState, type ReactElement } from "react";

import type { QuestionAnswer } from "../api/client";
import { AnswerPanel } from "../features/ask/AnswerPanel";
import { EXAMPLE_QUESTIONS } from "../features/ask/model";
import { QuestionForm } from "../features/ask/QuestionForm";
import { useProject } from "../state/ProjectContext";
import { useLocale } from "../state/LocaleContext";
import { jurisdictionName } from "../theme/jurisdictions";

/**
 * Questions against the project bible and the jurisdiction's legal corpus.
 * The view holds the one answer on screen and the request state; the data
 * layer sends the question under the project's current jurisdiction. A
 * question that fails leaves the last answer standing with the failure in
 * view, so nothing the reader was looking at disappears.
 */
export function AskView(): ReactElement {
  const { ask, jurisdictionCode, projectId, project, analysis } = useProject();
  const { text, locale } = useLocale();
  const [scene, setScene] = useState("");
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; window.speechSynthesis?.cancel(); }; }, []);
  const [answer, setAnswer] = useState<QuestionAnswer | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAsk(question: string): Promise<void> {
    setSubmitting(true);
    setError(null);
    const outcome = await ask(scene ? `[Scene: ${scene}] ${question}` : question);
    if (!alive.current) return;
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
        <h2>{text("Ask ClearCut", "Pregunta a ClearCut")}</h2>
        <p className="ask__lede">
          {text("Questions for", "Preguntas sobre")} {project?.title ?? projectId} · {jurisdictionName(jurisdictionCode, locale)}
        </p>
      </header>
      {analysis && <label className="ask__scene">{text("Scene context", "Contexto de escena")}<select value={scene} onChange={event => setScene(event.target.value)}><option value="">{text("Whole project", "Proyecto completo")}</option>{analysis.scenes.map(item => <option key={item.number} value={item.heading}>{item.number}. {item.heading}</option>)}</select></label>}
      <QuestionForm
        projectId={projectId}
        context={`${project?.title ?? projectId}${scene ? ` · ${scene}` : ""}`}
        examples={EXAMPLE_QUESTIONS}
        submitting={submitting}
        error={error}
        onAsk={(question) => void handleAsk(question)}
      />
      {answer !== null && <><AnswerPanel answer={answer} />{typeof window.speechSynthesis !== "undefined" && <div className="ask__listen"><button className="button" onClick={() => { window.speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(answer.text); utterance.lang = locale === "es" ? "es-419" : "en-US"; window.speechSynthesis.speak(utterance); }}>{text("Listen to answer", "Escuchar respuesta")}</button><button className="button" onClick={() => window.speechSynthesis.cancel()}>{text("Stop listening", "Detener lectura")}</button></div>}</>}
    </section>
  );
}
