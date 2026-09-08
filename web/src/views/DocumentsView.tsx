import { useEffect, useRef, useState } from "react";
import { downloadDocument, listDocuments, uploadDocument, type ProjectDocument } from "../api/client";
import { downloadBlob } from "../features/editor/download";
import { useLocale } from "../state/LocaleContext";
import { useProject } from "../state/ProjectContext";

export function DocumentsView() {
  const { projectId } = useProject();
  const { text } = useLocale();
  const [documents, setDocuments] = useState<ProjectDocument[]>([]);
  const [more, setMore] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const alive = useRef(true);
  const scope = useRef(projectId);
  scope.current = projectId;
  const current = () => alive.current && scope.current === projectId;
  useEffect(() => {
    alive.current = true;
    let active = true;
    setDocuments([]); setMore(null); setLoading(true); setUploading(false); setError(null);
    void listDocuments(projectId).then(page => { if (active && current()) { setDocuments(page.documents); setMore(page.next_before); } }).catch(() => { if (active && current()) setError(text("Could not load documents.", "No se pudieron cargar los documentos.")); }).finally(() => { if (active && current()) setLoading(false); });
    return () => { active = false; alive.current = false; };
  }, [projectId]);
  const upload = async (file: File) => {
    if (!file.size || file.size > 25 * 1024 * 1024) { setError(text("Choose a file up to 25 MiB.", "Elige un archivo de hasta 25 MiB.")); return; }
    setUploading(true); setError(null);
    try { const document = await uploadDocument(projectId, file); if (current()) setDocuments(items => [document, ...items]); }
    catch { if (current()) setError(text("Upload failed. Try again.", "No se pudo subir el archivo. Inténtalo de nuevo.")); }
    finally { if (current()) setUploading(false); }
  };
  const download = async (document: ProjectDocument) => {
    try { const blob = await downloadDocument(projectId, document.file_id); if (current()) downloadBlob(blob, document.filename); }
    catch { if (current()) setError(text("Download failed.", "No se pudo descargar.")); }
  };
  return <section className="documents-view">
    <h2>{text("Documents", "Documentos")}</h2>
    <p>{text("Original screenplays and project evidence. Uploading evidence does not mark a clearance as resolved.", "Guiones originales y evidencias del proyecto. Subir evidencia no resuelve una autorización.")}</p>
    <label>{text("Upload evidence or document", "Subir evidencia o documento")}<input type="file" disabled={uploading} onChange={event => { const file = event.target.files?.[0]; if (file) void upload(file); event.target.value = ""; }} /></label>
    {uploading && <p role="status">{text("Uploading…", "Subiendo…")}</p>}
    {error && <p role="alert">{error}</p>}
    {loading ? <p role="status">{text("Loading documents…", "Cargando documentos…")}</p> : documents.length === 0 ? <p>{text("No documents yet. Import a screenplay or upload evidence.", "Aún no hay documentos. Importa un guion o sube evidencia.")}</p> : <ul className="documents-view__list">{documents.map(document => <li key={document.file_id}><div><strong>{document.filename}</strong><p>{document.kind === "original" ? text("Original screenplay", "Guion original") : text("Project document", "Documento del proyecto")} · {Math.ceil(document.size_bytes / 1024)} KB · {new Date(document.created_at).toLocaleDateString()}</p></div><button className="button" onClick={() => void download(document)}>{text("Download", "Descargar")}</button></li>)}</ul>}
    {more && <button className="button" onClick={() => void listDocuments(projectId, more).then(page => { if (current()) { setDocuments(items => [...items, ...page.documents]); setMore(page.next_before); } }).catch(() => { if (current()) setError(text("Could not load more documents.", "No se pudieron cargar más documentos.")); })}>{text("Load older documents", "Cargar documentos anteriores")}</button>}
  </section>;
}
