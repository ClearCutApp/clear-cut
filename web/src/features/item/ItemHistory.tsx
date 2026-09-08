import { useEffect, useState, type ReactElement } from "react";

import { listTrackerItemHistory, type TrackerAuditEvent } from "../../api/client";
import { ErrorNotice } from "../../components/atoms/ErrorNotice";
import { useLocale } from "../../state/LocaleContext";

export function ItemHistory({ projectId, itemId, version }: { projectId: string; itemId: string; version: number }): ReactElement {
  const { text } = useLocale();
  const [opened, setOpened] = useState(false);
  const [events, setEvents] = useState<TrackerAuditEvent[]>([]);
  const [cursor, setCursor] = useState<number | undefined>();
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setEvents([]);
    setCursor(undefined);
    setOpened(false);
    setError(null);
  }, [projectId, itemId, version]);
  useEffect(() => {
    if (!opened) return;
    let active = true;
    setBusy(true);
    setError(null);
    void listTrackerItemHistory(projectId, itemId, cursor).then((rows) => {
      if (!active) return;
      setEvents((current) => cursor === undefined ? rows : [...new Map([...current, ...rows].map((event) => [event.event_id, event])).values()]);
      setMore(rows.length === 50);
    }).catch(() => {
      if (active) setError(text("History could not be loaded.", "No se pudo cargar el historial."));
    }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [opened, projectId, itemId, cursor, text]);
  return (
    <section className="item-panel__note" aria-label={text("Clearance history", "Historial de autorización")}>
      <button type="button" className="button button--quiet" aria-expanded={opened} onClick={() => setOpened(!opened)}>
        {text("Clearance history", "Historial de autorización")}
      </button>
      {opened && <>
        {busy && <p role="status">{text("Loading history…", "Cargando historial…")}</p>}
        <ErrorNotice message={error} />
        {!busy && events.length === 0 && !error && <p>{text("No recorded changes yet.", "Aún no hay cambios registrados.")}</p>}
        <ol>{events.map((event) => <li key={event.event_id}>
          <strong>{text("Version", "Versión")} {event.version} · {event.item.state}</strong>
          <p>{event.actor} · <time dateTime={event.at}>{event.at}</time></p>
        </li>)}</ol>
        {more && <button type="button" className="button button--quiet" disabled={busy} onClick={() => setCursor(events.at(-1)?.version)}>{text("Earlier changes", "Cambios anteriores")}</button>}
        <p>{text("History begins with recorded workspace events. Earlier legacy rows may be incomplete.", "El historial comienza con los eventos registrados del espacio. Los registros anteriores pueden estar incompletos.")}</p>
      </>}
    </section>
  );
}
