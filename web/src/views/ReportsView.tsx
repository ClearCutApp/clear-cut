import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import {
  ApiError, createReport, downloadReport, getReportContext, listReports,
  type ClearanceReport, type ReportSnapshotContext,
} from "../api/client";
import { downloadBlob } from "../features/editor/download";
import { useLocale } from "../state/LocaleContext";
import { useProject } from "../state/ProjectContext";

export function ReportsView() {
  const { projectId } = useProject();
  const { text, locale } = useLocale();
  const [reports, setReports] = useState<ClearanceReport[]>([]);
  const [snapshot, setSnapshot] = useState<ReportSnapshotContext | null>(null);
  const [configured, setConfigured] = useState(true);
  const [more, setMore] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const scope = useRef<object>({});

  useEffect(() => {
    const current = {};
    scope.current = current;
    setReports([]); setSnapshot(null); setMore(null); setLoading(true); setBusy(false); setError(null);
    void Promise.all([listReports(projectId), getReportContext(projectId)])
      .then(([page, context]) => {
        if (scope.current !== current) return;
        setReports(page.reports); setMore(page.next_before);
        setConfigured(context.configured); setSnapshot(context.snapshot);
      })
      .catch(() => { if (scope.current === current) setError(text("Could not load reports.", "No se pudieron cargar los informes.")); })
      .finally(() => { if (scope.current === current) setLoading(false); });
    return () => { scope.current = {}; };
  }, [projectId, reload, text]);

  const capture = async () => {
    if (!snapshot) return;
    const current = scope.current;
    setBusy(true); setError(null);
    try {
      const report = await createReport(projectId, snapshot, locale);
      if (scope.current === current) setReports(items => [report, ...items]);
    } catch (cause) {
      if (scope.current !== current) return;
      if (cause instanceof ApiError && cause.status === 409) {
        setSnapshot(null);
        setError(text("Clearances changed. Refresh the snapshot before creating a report.", "Las autorizaciones cambiaron. Actualiza la captura antes de crear el informe."));
      } else setError(text("Could not create the report. Your saved reports are unchanged.", "No se pudo crear el informe. Los informes guardados se conservan."));
    } finally { if (scope.current === current) setBusy(false); }
  };

  const download = async (report: ClearanceReport, format: "pdf" | "csv") => {
    const current = scope.current;
    try {
      const blob = await downloadReport(projectId, report.report_id, format);
      if (scope.current === current) downloadBlob(blob, `clearance-report-${report.report_id}.${format}`);
    } catch { if (scope.current === current) setError(text("Could not download the saved report.", "No se pudo descargar el informe guardado.")); }
  };

  const older = async () => {
    if (!more) return;
    const current = scope.current;
    setBusy(true);
    try {
      const page = await listReports(projectId, more);
      if (scope.current === current) { setReports(items => [...items, ...page.reports]); setMore(page.next_before); }
    } catch { if (scope.current === current) setError(text("Could not load older reports.", "No se pudieron cargar los informes anteriores.")); }
    finally { if (scope.current === current) setBusy(false); }
  };

  return <section className="documents-view">
    <h2>{text("Clearance reports", "Informes de autorizaciones")}</h2>
    <p>{text("Save an immutable record of one analyzed revision and its reviewed clearance state. Later edits do not change saved downloads.", "Guarda un registro inmutable de una revisión analizada y sus autorizaciones. Las ediciones posteriores no cambian las descargas guardadas.")}</p>
    {loading && <p role="status">{text("Loading reports…", "Cargando informes…")}</p>}
    {error && <p role="alert">{error}</p>}
    {!loading && !configured && <p>{text("Saved revision reports are unavailable in this demo. Explore screenplay PDF exports in the editor.", "Los informes de revisiones guardadas no están disponibles en esta demostración. Puedes explorar la exportación de guiones PDF en el editor.")}</p>}
    {!loading && configured && !snapshot && !error && <p>{text("Analyze a saved revision before creating a report.", "Analiza una revisión guardada antes de crear un informe.")} <Link to={`/projects/${encodeURIComponent(projectId)}/analyze`}>{text("Analyze revision", "Analizar revisión")}</Link></p>}
    {snapshot && <div className="revision-status">
      <strong>{text("Revision", "Revisión")} {snapshot.revision_id}</strong>
      <p>{snapshot.counts.confirmed_cleared} / {snapshot.counts.total_retained} {text("retained items confirmed cleared", "elementos conservados con autorización confirmada")} · {snapshot.counts.needs_review} {text("need review", "requieren revisión")}</p>
      <p>{text("Items requiring another review are excluded from confirmed clearances. Items no longer detected remain in the total and are identified in the report.", "Los elementos que requieren otra revisión no cuentan como autorizaciones confirmadas. Los que ya no se detectan permanecen en el total y se identifican en el informe.")}</p>
      <button className="button button--primary" disabled={busy} onClick={() => void capture()}>{busy ? text("Saving report…", "Guardando informe…") : text("Save report", "Guardar informe")}</button>
    </div>}
    {!loading && configured && <button className="button" disabled={busy} onClick={() => setReload(value => value + 1)}>{text("Refresh snapshot", "Actualizar captura")}</button>}
    {!loading && reports.length === 0 && <p>{text("No saved reports yet.", "Aún no hay informes guardados.")}</p>}
    <ul className="documents-view__list">{reports.map(report => <li key={report.report_id}>
      <div><strong>{text("Revision", "Revisión")} {report.revision_id}</strong><p>{new Date(report.created_at).toLocaleString(locale)} · {report.language.toUpperCase()} · {report.counts.confirmed_cleared}/{report.counts.total_retained} {text("confirmed", "confirmados")}</p></div>
      <button className="button" onClick={() => void download(report, "pdf")}>PDF</button>
      <button className="button" onClick={() => void download(report, "csv")}>CSV</button>
    </li>)}</ul>
    {more && <button className="button" disabled={busy} onClick={() => void older()}>{text("Older reports", "Informes anteriores")}</button>}
  </section>;
}
