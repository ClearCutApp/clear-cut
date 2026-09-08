import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { ApiError, downloadDocument, searchProject, type ProjectSearchPage, type ProjectSearchResult } from "../api/client";
import { downloadBlob } from "../features/editor/download";
import { useLocale } from "../state/LocaleContext";
import { useProject } from "../state/ProjectContext";

export function SearchView() {
  const { projectId, selectItem } = useProject();
  const { text } = useLocale();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [page, setPage] = useState<ProjectSearchPage | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scope = useRef<object>({});
  useEffect(() => {
    scope.current = {}; setQuery(""); setSubmitted(""); setPage(null); setBusy(false); setError(null);
    return () => { scope.current = {}; };
  }, [projectId]);
  const search = async (more = false) => {
    const current = scope.current;
    const value = more ? submitted : query.trim();
    setBusy(true); setError(null);
    if (!more) { setSubmitted(value); setPage(null); }
    try {
      const result = await searchProject(projectId, value, more ? page?.next_cursor ?? undefined : undefined);
      if (scope.current === current) setPage(previous => more && previous ? { ...result, results: [...previous.results, ...result.results] } : result);
    } catch (failure) {
      if (scope.current === current) {
        setError(failure instanceof ApiError && failure.status === 409
          ? text("Results changed. Search again to see the current matches.", "Los resultados cambiaron. Busca de nuevo para ver las coincidencias actuales.")
          : text("Search is unavailable. Your query is preserved; try again.", "La búsqueda no está disponible. Tu consulta se conserva; inténtalo de nuevo."));
      }
    } finally { if (scope.current === current) setBusy(false); }
  };
  const submit = (event: FormEvent) => { event.preventDefault(); void search(); };
  const open = async (result: ProjectSearchResult) => {
    const root = `/projects/${encodeURIComponent(projectId)}`;
    if (result.kind === "clearance") { selectItem(result.id); return; }
    if (result.kind === "script") {
      navigate(`${root}/editor?revision=${encodeURIComponent(result.revision_id ?? "")}&scene=${encodeURIComponent(result.scene_id ?? "")}`); return;
    }
    if (result.kind === "research") { navigate(`${root}/settings#research-${encodeURIComponent(result.id)}`); return; }
    const current = scope.current;
    setBusy(true); setError(null);
    try {
      const blob = await downloadDocument(projectId, result.id);
      if (scope.current === current) downloadBlob(blob, result.title);
    } catch { if (scope.current === current) setError(text("The document could not be downloaded.", "No se pudo descargar el documento.")); }
    finally { if (scope.current === current) setBusy(false); }
  };
  const label = (kind: ProjectSearchResult["kind"]) => ({
    script: text("Saved screenplay", "Guion guardado"), clearance: text("Clearance", "Autorización"),
    document: text("Document", "Documento"), research: text("Local research", "Investigación local"),
  })[kind];
  return <section className="documents-view">
    <h2>{text("Search this project", "Buscar en este proyecto")}</h2>
    <p>{text("Search the latest saved revision, current clearance details, document names and the latest 50 local research records. Unsaved drafts, document contents and older revisions are not searched.", "Busca en la última revisión guardada, los datos actuales de autorizaciones, nombres de documentos y los últimos 50 registros de investigación local. No se buscan borradores sin guardar, contenidos de documentos ni revisiones anteriores.")}</p>
    <form onSubmit={submit} className="field">
      <label htmlFor="project-search">{text("Words or phrase", "Palabras o frase")}</label>
      <input id="project-search" type="search" minLength={2} maxLength={200} required value={query} onChange={event => setQuery(event.target.value)} disabled={busy} />
      <button className="button" disabled={busy || query.trim().length < 2}>{text("Search", "Buscar")}</button>
    </form>
    {busy && <p role="status">{text("Searching…", "Buscando…")}</p>}
    {error && <p role="alert">{error}</p>}
    {page && <p role="status">{page.total} {text("matches for", "coincidencias para")} “{submitted}”</p>}
    <ul className="documents-view__list">{page?.results.map(result => <li key={`${result.kind}:${result.id}`}>
      <div><strong>{result.title}</strong><p>{label(result.kind)}{result.revision_id ? ` · ${result.revision_id}` : ""}</p>
        <p style={{ whiteSpace: "pre-wrap" }}>{result.excerpt}</p>
      </div>
      <button className="button button--secondary" disabled={busy} onClick={() => void open(result)}>{result.kind === "document" ? text("Download", "Descargar") : text("Open", "Abrir")}</button>
    </li>)}</ul>
    {page?.next_cursor && <button className="button" disabled={busy} onClick={() => void search(true)}>{text("More matches", "Más coincidencias")}</button>}
  </section>;
}
