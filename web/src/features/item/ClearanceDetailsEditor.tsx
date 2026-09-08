import { useEffect, useRef, useState, type ReactElement } from "react";

import {
  downloadDocument, downloadPermissionRequest, listDocuments, updateClearanceDetails, uploadDocument,
  type ClearanceDetails, type ProjectDocument, type TrackerItem,
} from "../../api/client";
import { ErrorNotice } from "../../components/atoms/ErrorNotice";
import { useLocale } from "../../state/LocaleContext";
import { downloadBlob } from "../editor/download";
import { ProjectAssigneeSelect } from "./ProjectAssigneeSelect";

function values(item: TrackerItem): ClearanceDetails {
  return {
    note: item.note, clearance_conditions: item.clearance_conditions ?? "",
    due_date: item.due_date ?? "", assignee_id: item.assignee_id ?? "",
    evidence_file_ids: item.evidence_file_ids ?? [], draft_email: item.draft_email,
  };
}

export function ClearanceDetailsEditor({ item, onSaved }: { item: TrackerItem; onSaved: () => void }): ReactElement {
  const { text } = useLocale();
  const [opened, setOpened] = useState(false);
  const [details, setDetails] = useState(() => values(item));
  const [version, setVersion] = useState(item.version);
  const [documents, setDocuments] = useState<ProjectDocument[]>([]);
  const [more, setMore] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const active = useRef(true);
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  useEffect(() => {
    if (!opened) return;
    form.current?.querySelector("textarea")?.focus();
    let current = true;
    void listDocuments(item.project_id).then((page) => {
      if (current) { setDocuments(page.documents); setMore(page.next_before); }
    }).catch(() => {
      if (current) setError(text("Documents could not be loaded. Your edits are preserved.", "No se pudieron cargar los documentos. Tus cambios se conservan."));
    });
    return () => { current = false; };
  }, [opened, item.project_id, text]);

  const upload = async (file: File) => {
    if (!file.size || file.size > 25 * 1024 * 1024 || details.evidence_file_ids.length >= 20) {
      setError(text("Choose a file up to 25 MiB; each item supports 20 evidence files.", "Elige un archivo de hasta 25 MiB; cada elemento admite 20 evidencias."));
      return;
    }
    setBusy(true); setError(null);
    try {
      const document = await uploadDocument(item.project_id, file);
      if (!active.current) return;
      setDocuments((current) => [document, ...current]);
      setDetails((current) => ({ ...current, evidence_file_ids: [...current.evidence_file_ids, document.file_id] }));
    } catch {
      if (active.current) setError(text("Upload failed. Your edits are preserved.", "No se pudo subir el archivo. Tus cambios se conservan."));
    } finally { if (active.current) setBusy(false); }
  };

  const save = async () => {
    setBusy(true); setError(null);
    try {
      await updateClearanceDetails(item.project_id, item.item_id, version, details);
      if (!active.current) return;
      setOpened(false); onSaved();
    } catch (failure) {
      if (active.current) setError(failure instanceof Error ? failure.message : text("Save failed. Your edits are preserved.", "No se pudo guardar. Tus cambios se conservan."));
    } finally { if (active.current) setBusy(false); }
  };

  return <section className="item-facts clearance-details">
    <h3>{text("Evidence and permission details", "Evidencia y condiciones de autorización")}</h3>
    {!opened ? <>
      {item.due_date && <p>{text("Due", "Vence")}: {item.due_date}</p>}
      {item.clearance_conditions && <p>{item.clearance_conditions}</p>}
      {item.draft_email && <div>{(["pdf", "txt"] as const).map((format) => <button key={format} type="button" className="button button--quiet" onClick={() => void downloadPermissionRequest(item.project_id, item.item_id, item.version, format).then((blob) => { if (active.current) downloadBlob(blob, `permission-request-v${item.version}.${format}`); }).catch((failure) => { if (active.current) setError(failure instanceof Error ? failure.message : text("Download failed.", "No se pudo descargar.")); })}>{format === "pdf" ? text("Request PDF", "Solicitud PDF") : text("Editable request TXT", "Solicitud editable TXT")}</button>)}</div>}
      <ErrorNotice message={error} />
      <p>{(item.evidence_file_ids ?? []).length} {text("linked evidence files", "archivos de evidencia vinculados")}</p>
      <button type="button" className="button button--quiet" onClick={() => { setDetails(values(item)); setVersion(item.version); setError(null); setOpened(true); }}>{text("Edit details and evidence", "Editar condiciones y evidencia")}</button>
    </> : <form ref={form} onSubmit={(event) => { event.preventDefault(); void save(); }}>
      <fieldset disabled={busy}>
        <label>{text("Note", "Nota")}<textarea maxLength={4000} value={details.note} onChange={(event) => setDetails({ ...details, note: event.target.value })} /></label>
        <label>{text("Clearance conditions", "Condiciones de autorización")}<textarea maxLength={4000} value={details.clearance_conditions} onChange={(event) => setDetails({ ...details, clearance_conditions: event.target.value })} /></label>
        <label>{text("Due date", "Fecha de vencimiento")}<input type="date" value={details.due_date} onChange={(event) => setDetails({ ...details, due_date: event.target.value })} /></label>
        <ProjectAssigneeSelect projectId={item.project_id} value={details.assignee_id} onChange={value => setDetails({ ...details, assignee_id: value })} />
        <label>{text("Permission-request draft", "Borrador de solicitud de permiso")}<textarea rows={8} maxLength={20000} value={details.draft_email ?? ""} onChange={(event) => setDetails({ ...details, draft_email: event.target.value })} /></label>
        <p>{text("This draft is never sent automatically. Saving evidence does not change clearance status.", "Este borrador nunca se envía automáticamente. Guardar evidencia no cambia el estado de autorización.")}</p>
        <label>{text("Upload evidence", "Subir evidencia")}<input type="file" onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file); event.target.value = ""; }} /></label>
        {documents.map((document) => <div key={document.file_id}>
          <label><input type="checkbox" checked={details.evidence_file_ids.includes(document.file_id)} onChange={(event) => setDetails({ ...details, evidence_file_ids: event.target.checked ? [...details.evidence_file_ids, document.file_id] : details.evidence_file_ids.filter((id) => id !== document.file_id) })} />{document.filename}</label>
          <button type="button" className="button button--quiet" onClick={() => void downloadDocument(item.project_id, document.file_id).then((blob) => { if (active.current) downloadBlob(blob, document.filename); }).catch(() => { if (active.current) setError(text("Download failed.", "No se pudo descargar.")); })}>{text("Download", "Descargar")}</button>
        </div>)}
        {more && <button type="button" className="button button--quiet" onClick={() => void listDocuments(item.project_id, more).then((page) => { if (active.current) { setDocuments((current) => [...current, ...page.documents]); setMore(page.next_before); } }).catch(() => { if (active.current) setError(text("Could not load older documents.", "No se pudieron cargar documentos anteriores.")); })}>{text("Older documents", "Documentos anteriores")}</button>}
        <button type="submit" className="button button--primary">{text("Save details", "Guardar condiciones")}</button>
        <button type="button" className="button button--quiet" onClick={() => setOpened(false)}>{text("Cancel edits", "Cancelar cambios")}</button>
      </fieldset>
      {busy && <p role="status">{text("Saving…", "Guardando…")}</p>}
      <ErrorNotice message={error} />
    </form>}
  </section>;
}
