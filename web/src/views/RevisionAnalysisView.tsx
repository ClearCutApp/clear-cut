import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { cancelAnalysis, listRevisions, type ScreenplayRevision } from "../api/client";
import { useProject } from "../state/ProjectContext";
import { useLocale } from "../state/LocaleContext";

export function RevisionAnalysisView() {
  const { projectId, jurisdictionCode, runAnalysis, job } = useProject();
  const { text } = useLocale();
  const navigate = useNavigate();
  const [revisions, setRevisions] = useState<ScreenplayRevision[] | null>(null);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void listRevisions(projectId).then(page => {
      if (!active) return;
      setRevisions(page.revisions);
      setSelected(page.revisions[0]?.revision_id ?? "");
    }).catch(() => { if (active) setError(text("Revision history could not be loaded.", "No se pudo cargar el historial de revisiones.")); });
    return () => { active = false; };
  }, [projectId, text]);

  async function analyze() {
    setBusy(true); setError("");
    const result = await runAnalysis({ revision_id: selected, jurisdiction_code: jurisdictionCode });
    setBusy(false);
    if (result.ok) void navigate(`/projects/${encodeURIComponent(projectId)}/script`);
    else setError(result.message);
  }
  async function cancel() {
    if (!job) return;
    setCancelling(true);
    try { await cancelAnalysis(projectId, job.analysis_id); }
    catch { setError(text("Cancellation could not be confirmed. Try again.", "No se pudo confirmar la cancelación. Inténtalo de nuevo.")); }
    finally { setCancelling(false); }
  }
  const running = job?.state === "QUEUED" || job?.state === "RUNNING";
  return <section className="analyze">
    <h2>{text("Analyze a saved revision", "Analizar una revisión guardada")}</h2>
    <p>{text("Choose an immutable revision. You can keep writing while analysis runs; its findings stay attached to the selected revision.", "Elige una revisión inmutable. Puedes seguir escribiendo durante el análisis; los hallazgos seguirán vinculados a la revisión seleccionada.")}</p>
    <Link to={`/projects/${encodeURIComponent(projectId)}/editor`}>{text("Open screenplay and save a revision", "Abrir el guion y guardar una revisión")}</Link>
    {revisions === null && !error && <p role="status">{text("Loading revisions…", "Cargando revisiones…")}</p>}
    {revisions?.length === 0 && <p>{text("Save your first revision in the screenplay editor before analyzing.", "Guarda la primera revisión en el editor antes de analizar.")}</p>}
    {!!revisions?.length && <form onSubmit={event => { event.preventDefault(); void analyze(); }}>
      <label>{text("Saved revision", "Revisión guardada")}<select value={selected} disabled={busy || running} onChange={event => setSelected(event.target.value)}>
        {revisions.map(revision => <option key={revision.revision_id} value={revision.revision_id}>{text("Revision", "Revisión")} {revision.draft_version} · {new Date(revision.created_at).toLocaleString()}</option>)}
      </select></label>
      <button type="submit" disabled={busy || running || !selected}>{text("Analyze revision", "Analizar revisión")}</button>
    </form>}
    {running && <div role="status"><p>{text("Analysis in progress", "Análisis en curso")} · {job.stage ?? job.state}</p>
      <button type="button" onClick={() => void cancel()} disabled={cancelling}>{text("Cancel analysis", "Cancelar análisis")}</button>
      <p>{text("Cancellation prevents publication. Research already submitted to a provider may continue.", "La cancelación impide publicar resultados. Una investigación ya enviada a un proveedor puede continuar.")}</p>
    </div>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
