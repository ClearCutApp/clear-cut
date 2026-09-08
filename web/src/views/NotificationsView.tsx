import { useEffect, useRef, useState } from "react";
import { getProjectNotifications, readProjectNotification, type ProjectNotification } from "../api/client";
import { useLocale } from "../state/LocaleContext";
import { useProject } from "../state/ProjectContext";

export function NotificationsView() {
  const { projectId, selectItem } = useProject();
  const { text, locale } = useLocale();
  const [records, setRecords] = useState<ProjectNotification[]>([]);
  const [more, setMore] = useState<string | null>(null);
  const [configured, setConfigured] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const scope = useRef<object>({});
  useEffect(() => {
    const current = {};
    scope.current = current;
    setRecords([]); setMore(null); setLoading(true); setError(false);
    void getProjectNotifications(projectId).then(page => {
      if (scope.current !== current) return;
      setConfigured(page.configured); setRecords(page.notifications); setMore(page.next_cursor);
    }).catch(() => { if (scope.current === current) setError(true); })
      .finally(() => { if (scope.current === current) setLoading(false); });
    return () => { scope.current = {}; };
  }, [projectId, refresh]);
  const older = async () => {
    if (!more) return;
    const current = scope.current;
    setLoading(true); setError(false);
    try {
      const page = await getProjectNotifications(projectId, more);
      if (scope.current === current) {
        setRecords(previous => [...previous, ...page.notifications]); setMore(page.next_cursor);
      }
    } catch { if (scope.current === current) setError(true); }
    finally { if (scope.current === current) setLoading(false); }
  };
  const markRead = async (id: string) => {
    const current = scope.current;
    setLoading(true); setError(false);
    try {
      await readProjectNotification(projectId, id);
      if (scope.current === current) setRecords(previous => previous.map(value => value.notification_id === id ? { ...value, read: true } : value));
    } catch { if (scope.current === current) setError(true); }
    finally { if (scope.current === current) setLoading(false); }
  };
  const delivery = (record: ProjectNotification) => ({
    in_app_only: text("In this project", "En este proyecto"),
    queued: text("External notification queued", "Notificación externa en cola"),
    pending: text("External delivery pending", "Envío externo pendiente"),
    delivering: text("External delivery in progress", "Envío externo en curso"),
    delivered: text("External destination accepted", "Destino externo confirmado"),
    blocked: text("External destination unavailable", "Destino externo no disponible"),
    failed: text("External delivery unconfirmed", "Envío externo sin confirmar"),
  })[record.delivery];
  return <section className="documents-view">
    <h2>{text("Notifications", "Notificaciones")}</h2>
    <p>{text("Private requests for attention on this project. A notification never changes clearance status.", "Solicitudes privadas de atención en este proyecto. Una notificación nunca cambia el estado de autorización.")}</p>
    {error && <p role="alert">{text("Notifications could not be updated. Please try again.", "No se pudieron actualizar las notificaciones. Inténtalo de nuevo.")}</p>}
    {loading && <p role="status">{text("Loading…", "Cargando…")}</p>}
    {!configured && !loading && <p>{text("Notifications are unavailable in this isolated demo.", "Las notificaciones no están disponibles en esta demostración aislada.")}</p>}
    {configured && <button className="button" disabled={loading} onClick={() => setRefresh(value => value + 1)}>{text("Refresh", "Actualizar")}</button>}
    {!loading && configured && !error && records.length === 0 && <p>{text("No notifications yet.", "Aún no hay notificaciones.")}</p>}
    <ul className="documents-view__list">{records.map(record => <li key={record.notification_id}>
      <div><strong>{record.item_id} · {text("Version", "Versión")} {record.item_version}</strong>
        <p style={{ whiteSpace: "pre-wrap" }}>{record.reason}</p>
        <p>{new Date(record.created_at).toLocaleString(locale)} · {delivery(record)}</p>
        <button className="button button--secondary" onClick={() => selectItem(record.item_id)}>{text("Open clearance", "Abrir autorización")}</button>
      </div>
      {record.read ? <span>{text("Read", "Leída")}</span> : <button className="button" disabled={loading} onClick={() => void markRead(record.notification_id)}>{text("Mark read", "Marcar como leída")}</button>}
    </li>)}</ul>
    {more && <button className="button" disabled={loading} onClick={() => void older()}>{text("Older notifications", "Notificaciones anteriores")}</button>}
  </section>;
}
