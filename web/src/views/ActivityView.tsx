import { useEffect, useRef, useState } from "react";
import { getProjectActivity, type ActivityEvent } from "../api/client";
import { useLocale } from "../state/LocaleContext";
import { useProject } from "../state/ProjectContext";

export function ActivityView() {
  const { projectId } = useProject();
  const { text, locale } = useLocale();
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [trends, setTrends] = useState<ActivityEvent[]>([]);
  const [more, setMore] = useState<string | null>(null);
  const [configured, setConfigured] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const scope = useRef<object>({});
  useEffect(() => {
    const current = {};
    scope.current = current;
    setEvents([]); setTrends([]); setMore(null); setLoading(true); setError(false);
    void getProjectActivity(projectId).then(page => {
      if (scope.current !== current) return;
      setConfigured(page.configured); setEvents(page.events); setTrends(page.trends); setMore(page.next_before);
    }).catch(() => { if (scope.current === current) setError(true); })
      .finally(() => { if (scope.current === current) setLoading(false); });
    return () => { scope.current = {}; };
  }, [projectId, refresh]);
  const older = async () => {
    if (!more) return;
    const current = scope.current;
    setLoading(true);
    try {
      const page = await getProjectActivity(projectId, more);
      if (scope.current === current) {
        setEvents(previous => [...previous, ...page.events]); setMore(page.next_before);
      }
    } catch { if (scope.current === current) setError(true); }
    finally { if (scope.current === current) setLoading(false); }
  };
  const title = (event: ActivityEvent) => ({
    project_created: text("Project created", "Proyecto creado"),
    revision_saved: text("Revision saved", "Revisión guardada"),
    document_created: text("Document added", "Documento añadido"),
    clearance_changed: text("Clearance updated", "Autorización actualizada"),
    analysis_published: text("Analysis completed", "Análisis completado"),
    report_created: text("Report saved", "Informe guardado"),
  })[event.kind] ?? text("Project updated", "Proyecto actualizado");
  return <section className="documents-view">
    <h2>{text("Project activity", "Actividad del proyecto")}</h2>
    <p>{text("Recorded changes and clearance counts at each completed analysis. Recent changes may take a moment to appear.", "Cambios registrados y recuentos de autorizaciones al completar cada análisis. Los cambios recientes pueden tardar un momento en aparecer.")}</p>
    {error && <p role="alert">{text("Activity is temporarily unavailable. Your project changes are still saved.", "La actividad no está disponible temporalmente. Los cambios del proyecto siguen guardados.")}</p>}
    {loading && <p role="status">{text("Loading activity…", "Cargando actividad…")}</p>}
    {!configured && !loading && <p>{text("Historical activity is unavailable in this isolated demo.", "El historial de actividad no está disponible en esta demostración aislada.")}</p>}
    {configured && <button className="button" disabled={loading} onClick={() => setRefresh(value => value + 1)}>{text("Refresh", "Actualizar")}</button>}
    {trends.length > 0 && <section>
      <h3>{text("Clearances at analysis completion", "Autorizaciones al completar el análisis")}</h3>
      <p>{text("Confirmed counts exclude items awaiting review and include all retained items in the total.", "Los recuentos confirmados excluyen elementos pendientes de revisión e incluyen todos los elementos conservados en el total.")}</p>
      <ul className="documents-view__list">{trends.map(event => <li key={event.event_id}>
        <div><strong>{event.payload.revision_id}</strong><p>{new Date(event.occurred_at).toLocaleString(locale)}</p></div>
        <span>{event.payload.counts?.confirmed_cleared !== undefined && event.payload.counts.total_retained !== undefined
          ? `${event.payload.counts.confirmed_cleared}/${event.payload.counts.total_retained} ${text("confirmed", "confirmados")}`
          : text("Counts not recorded", "Recuentos no registrados")}</span>
      </li>)}</ul>
    </section>}
    {!loading && configured && !error && events.length === 0 && <p>{text("No projected activity yet.", "Aún no hay actividad registrada.")}</p>}
    <ul className="documents-view__list">{events.map(event => <li key={event.event_id}>
      <div><strong>{title(event)}</strong><p>{event.payload.item_id ?? event.payload.revision_id ?? ""} · {new Date(event.occurred_at).toLocaleString(locale)}</p></div>
      {event.payload.needs_review && <span>{text("Needs review", "Requiere revisión")}</span>}
    </li>)}</ul>
    {more && <button className="button" disabled={loading} onClick={() => void older()}>{text("Older activity", "Actividad anterior")}</button>}
    <p className="item-panel__note">{text("Activity and analysis trends powered by ClickHouse.", "Actividad y evolución de los análisis con ClickHouse.")}</p>
  </section>;
}
