import { useEffect, useRef, useState } from "react";
import { ApiError, getProjectSettings, listLocalResearch, researchProductionLocation,
  type LocalResearchRecord, type ProjectSettings } from "../../api/client";
import { useLocale } from "../../state/LocaleContext";

export function LocalResearchPanel({ projectId, savedVersion, editable }: {
  projectId: string; savedVersion: number; editable: boolean;
}) {
  const { text } = useLocale();
  const [settings, setSettings] = useState<ProjectSettings | null>(null);
  const [records, setRecords] = useState<LocalResearchRecord[]>([]);
  const [question, setQuestion] = useState("");
  const [location, setLocation] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scope = useRef<object>({});
  useEffect(() => {
    const current = {}; scope.current = current;
    setSettings(null); setRecords([]); setQuestion(""); setLocation(0); setBusy(false); setError(null);
    void Promise.all([getProjectSettings(projectId), listLocalResearch(projectId)])
      .then(([saved, result]) => {
        if (scope.current === current) { setSettings(saved); setRecords(result.research); }
      }).catch(() => {
        if (scope.current === current) setError(text("Could not load local research.", "No se pudo cargar la investigación local."));
      });
    return () => { scope.current = {}; };
  }, [projectId, savedVersion, text]);

  useEffect(() => {
    if (window.location.hash.startsWith("#research-")) document.getElementById(window.location.hash.slice(1))?.scrollIntoView?.({ block: "center" });
  }, [records]);

  const research = async () => {
    if (!settings || !question.trim()) return;
    const current = scope.current;
    setBusy(true); setError(null);
    try {
      const result = await researchProductionLocation(projectId, settings.version, location, question);
      if (scope.current === current) setRecords(previous => [result, ...previous].slice(0, 50));
    } catch (cause) {
      if (scope.current === current) setError(cause instanceof ApiError && cause.status === 409
        ? text("Saved locations changed during research. Your question is preserved; reload saved settings before trying again.", "Las ubicaciones guardadas cambiaron durante la investigación. Tu pregunta se conserva; recarga la configuración antes de volver a intentarlo.")
        : text("Research could not be saved. Your question is preserved.", "No se pudo guardar la investigación. Tu pregunta se conserva."));
    } finally { if (scope.current === current) setBusy(false); }
  };

  return <section aria-labelledby="local-research-heading">
    <h2 id="local-research-heading">{text("Local requirements research", "Investigación de requisitos locales")}</h2>
    <p>{text("Search official sources with Parallel for a saved location. Research records evidence; it never grants permission or marks a clearance complete.", "Busca fuentes oficiales con Parallel para una ubicación guardada. La investigación registra evidencia; nunca concede permisos ni completa una autorización.")}</p>
    {settings && !settings.locations.length && <p>{text("Save a production location first.", "Primero guarda una ubicación de producción.")}</p>}
    {settings && settings.locations.length > 0 && editable && <form onSubmit={event => { event.preventDefault(); void research(); }}>
      <fieldset disabled={busy}>
        <label>{text("Saved location", "Ubicación guardada")}<select value={location} onChange={event => setLocation(Number(event.target.value))}>
          {settings.locations.map((value, index) => <option key={index} value={index}>{value.location} · {value.country}</option>)}
        </select></label>
        <label>{text("Local requirements question", "Pregunta sobre requisitos locales")}<textarea required maxLength={2000} value={question} onChange={event => setQuestion(event.target.value)} /></label>
        <button className="button button--primary" disabled={!question.trim()}>{busy ? text("Researching…", "Investigando…") : text("Research and save evidence", "Investigar y guardar evidencia")}</button>
      </fieldset>
    </form>}
    {error && <p role="alert">{error}</p>}
    {!records.length && <p>{text("No local evidence has been recorded. Permit requirements, authority and fees remain unknown.", "No hay evidencia local registrada. Los requisitos, la autoridad y las tasas de los permisos siguen sin determinarse.")}</p>}
    {records.map(record => <article key={record.research_id} id={`research-${record.research_id}`}>
      <h3>{record.location.location}</h3>
      <p>{record.question}</p>
      <p>{record.created_at} · {record.settings_version !== settings?.version ? text("Earlier production settings", "Configuración de producción anterior") : text("Current saved settings", "Configuración guardada actual")}</p>
      <p>{record.status === "coverage_gap" ? text("Coverage gap: no official evidence found.", "Laguna de cobertura: no se encontró evidencia oficial.") : text("Recorded evidence · human clearance still required", "Evidencia registrada · requiere autorización humana")}</p>
      {record.citations.map((citation, index) => <blockquote key={`${citation.uri}-${index}`}>
        <p>{citation.snippet}</p><a href={citation.uri} target="_blank" rel="noopener noreferrer">{citation.title || citation.uri}</a>
      </blockquote>)}
    </article>)}
  </section>;
}
