import { Mic, Square, X } from "lucide-react";
import { useState } from "react";
import type { SpeechLanguage } from "../../api/client";
import { useLocale } from "../../state/LocaleContext";
import { useServerMode } from "../../state/ServerModeContext";
import { useVoiceRecorder } from "./useVoiceRecorder";

export function VoiceQuestion({ projectId, context, onTranscript }: { projectId: string; context: string; onTranscript: (text: string) => void }) {
  const { locale, text } = useLocale();
  const mode = useServerMode();
  const [language, setLanguage] = useState<SpeechLanguage>(locale === "es" ? "es-419" : "en-US");
  const voice = useVoiceRecorder(projectId, onTranscript);
  const busy = voice.phase !== "idle";
  const errors: Record<string, string> = {
    unsupported: text("Recording is not supported here. Type your question below.", "Este navegador no permite grabar. Escribe tu pregunta abajo."),
    denied: text("Microphone permission was denied. Allow microphone access in your browser or type below.", "Se denegó el acceso al micrófono. Permítelo en el navegador o escribe abajo."),
    recording: text("The microphone could not record. Try again or type below.", "No se pudo grabar. Inténtalo de nuevo o escribe abajo."),
    "too-large": text("Recording exceeded 8 MiB. Try a shorter question.", "La grabación superó 8 MiB. Haz una pregunta más corta."),
    empty: text("The recording was empty. Try again or type below.", "La grabación está vacía. Inténtalo de nuevo o escribe abajo."),
    transcription: text("Transcription failed. Your existing text is safe. Record again or type below.", "No se pudo transcribir. Tu texto se conserva. Graba de nuevo o escribe abajo."),
  };
  return <section className="voice-question" aria-label={text("Voice question", "Pregunta por voz")}>
    <p className="voice-question__context">{context}</p>
    <h3>{text("Talk through your next question", "Haz tu próxima pregunta por voz")}</h3>
    <p>{text("Record up to a minute. Review the transcript, then ask.", "Graba hasta un minuto. Revisa la transcripción y envía la pregunta.")}</p>
    <label className="voice-question__language">{text("Recording language", "Idioma de grabación")}
      <select value={language} disabled={busy} onChange={event => setLanguage(event.target.value as SpeechLanguage)}>
        <option value="en-US">English</option><option value="es-419">Español (Latinoamérica)</option><option value="es-ES">Español (España)</option>
      </select>
    </label>
    <div className="voice-question__controls">
      {voice.phase === "recording" ? <button type="button" className="voice-question__record voice-question__record--active" onClick={voice.stop}><Square aria-hidden="true" />{text("Stop recording", "Detener grabación")} · {voice.seconds}s</button> : <button type="button" className="voice-question__record" disabled={busy || mode !== "live" || !voice.supported} onClick={() => void voice.start(language)}><Mic aria-hidden="true" />{text("Record question", "Grabar pregunta")}</button>}
      {busy && <button type="button" className="button" onClick={voice.cancel}><X aria-hidden="true" />{text("Cancel", "Cancelar")}</button>}
    </div>
    <p role="status">{voice.phase === "requesting" ? text("Waiting for microphone permission…", "Esperando permiso del micrófono…") : voice.phase === "transcribing" ? text("Uploading and transcribing…", "Enviando y transcribiendo…") : voice.phase === "recording" ? text("Recording. Your microphone is active.", "Grabando. El micrófono está activo.") : mode === "mock" ? text("Voice transcription is unavailable in this demo. Type a question below.", "La transcripción no está disponible en esta demostración. Escribe abajo.") : !voice.supported ? errors.unsupported : text("Audio is sent for transcription and is not saved in your project.", "El audio se envía para transcribirlo y no se guarda en el proyecto.")}</p>
    {voice.error && <p role="alert">{errors[voice.error]}</p>}
  </section>;
}
