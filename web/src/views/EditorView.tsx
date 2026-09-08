import { useEffect, useRef, useState, type ReactElement } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Link, useSearchParams } from "react-router";
import { ApiError, exportScreenplay, importScreenplay, freezeRevision, getDraft, getRevision, listRevisions, saveDraft, type ScreenplayDocument, type ScreenplayDraft, type ScreenplayRevision } from "../api/client";
import { DraftAutosave, type SaveState } from "../features/editor/autosave";
import { downloadBlob } from "../features/editor/download";
import { blockKinds, emptyScreenplay, ScreenplayAttributes } from "../features/editor/schema";
import { useProject } from "../state/ProjectContext";
import { useLocale } from "../state/LocaleContext";

export function EditorView(): ReactElement {
  const { projectId } = useProject();
  const { text } = useLocale();
  const [draft, setDraft] = useState<ScreenplayDraft | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    setDraft(null); setError(null);
    void getDraft(projectId).then(value => { if (current) setDraft(value); }).catch(() => { if (current) setError(text("Could not load screenplay.", "No se pudo cargar el guion.")); });
    return () => { current = false; };
  }, [projectId]);
  if (error) return <p role="alert">{error}</p>;
  if (!draft) return <p role="status">{text("Loading screenplay…", "Cargando guion…")}</p>;
  return <ScreenplayEditor key={`${projectId}-${draft.version}`} draft={draft} onReload={setDraft} />;
}

function ScreenplayEditor({ draft, onReload }: { draft: ScreenplayDraft; onReload: (draft: ScreenplayDraft) => void }): ReactElement {
  const { text } = useLocale();
  const [searchParams] = useSearchParams();
  const requestedRevision = searchParams.get("revision");
  const requestedScene = searchParams.get("scene");
  const initial = useRef(draft.document ?? emptyScreenplay());
  const [saveState, setSaveState] = useState<SaveState>({ version: draft.version, dirty: draft.document === null, saving: false, error: null });
  const [revisions, setRevisions] = useState<ScreenplayRevision[]>([]);
  const [more, setMore] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [preview, setPreview] = useState<ScreenplayRevision | null>(null);
  const [freezing, setFreezing] = useState(false);
  const [importing, setImporting] = useState(false);
  const autosave = useRef<DraftAutosave | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const alive = useRef(true);
  const editor = useEditor({
    extensions: [StarterKit.configure({ heading: false, blockquote: false, bulletList: false, orderedList: false, listItem: false, codeBlock: false, code: false, strike: false, horizontalRule: false, link: false, underline: false, trailingNode: false }), ScreenplayAttributes],
    content: initial.current,
    editorProps: { attributes: { "aria-label": text("Screenplay editor", "Editor de guion"), role: "textbox", "aria-multiline": "true" } },
    onUpdate: ({ editor: updated }) => {
      autosave.current?.change(updated.getJSON() as unknown as ScreenplayDocument);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => { void autosave.current?.flush().catch(() => undefined); }, 900);
    },
  });
  useEffect(() => {
    alive.current = true;
    const queue = new DraftAutosave(draft.version, (version, document) => saveDraft(draft.project_id, version, document), setSaveState);
    autosave.current = queue;
    if (!draft.document) queue.change(initial.current);
    void listRevisions(draft.project_id).then(page => { if (alive.current) { setRevisions(page.revisions); setMore(page.next_before_version); } }).catch(() => { if (alive.current) setNotice(text("History could not load.", "No se pudo cargar el historial.")); });
    return () => { alive.current = false; queue.dispose(); if (timer.current) clearTimeout(timer.current); };
  }, [draft]);
  useEffect(() => {
    if (!saveState.dirty) return;
    const preventLoss = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", preventLoss);
    return () => window.removeEventListener("beforeunload", preventLoss);
  }, [saveState.dirty]);
  useEffect(() => {
    if (!requestedRevision) return;
    let current = true;
    void getRevision(draft.project_id, requestedRevision).then(value => {
      if (current) setPreview(value);
    }).catch(() => { if (current) setNotice(text("The cited revision could not be loaded.", "No se pudo cargar la revisión citada.")); });
    return () => { current = false; };
  }, [draft.project_id, requestedRevision, text]);
  useEffect(() => {
    if (preview && requestedScene) document.getElementById(`revision-scene-${requestedScene}`)?.scrollIntoView?.({ block: "start" });
  }, [preview, requestedScene]);
  const conflict = saveState.error instanceof ApiError && saveState.error.status === 409;
  const saveRevision = async () => {
    setFreezing(true); setNotice(null);
    try {
      await autosave.current?.flush();
      const revision = await freezeRevision(draft.project_id, autosave.current?.version() ?? draft.version);
      if (alive.current) { setRevisions(items => [revision, ...items.filter(item => item.revision_id !== revision.revision_id)]); setNotice(text("Revision saved.", "Revisión guardada.")); }
    } catch { if (alive.current) setNotice(text("Revision was not saved. Your text is still here.", "No se guardó la revisión. El texto sigue aquí.")); }
    finally { if (alive.current) setFreezing(false); }
  };
  const importFile = async (file: File) => {
    if (file.size > 25 * 1024 * 1024) { setNotice(text("File exceeds 25 MiB.", "El archivo supera 25 MiB.")); return; }
    if (!window.confirm(text("Import this screenplay as the next draft? Existing saved revisions remain available.", "¿Importar este guion como próximo borrador? Las revisiones guardadas siguen disponibles."))) return;
    setImporting(true);
    editor?.setEditable(false);
    try {
      await autosave.current?.flush();
      const imported = await importScreenplay(draft.project_id, file, autosave.current?.version() ?? draft.version);
      if (alive.current) onReload(imported.draft);
    } catch {
      if (alive.current) setNotice(text("Import failed or the draft changed. Your editor text is preserved; uploaded originals are in Documents.", "No se pudo importar o el borrador cambió. El texto se conserva; los originales subidos están en Documentos."));
    } finally { if (alive.current) { setImporting(false); editor?.setEditable(true); } }
  };
  const downloadRevision = async (revisionId: string, format: "pdf" | "fdx") => {
    try { const blob = await exportScreenplay(draft.project_id, revisionId, format); if (alive.current) downloadBlob(blob, `screenplay-${revisionId}.${format}`); }
    catch { if (alive.current) setNotice(text("Download failed. Try again.", "No se pudo descargar. Inténtalo de nuevo.")); }
  };
  const downloadLocal = () => {
    if (!editor) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(editor.getJSON(), null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "clearcut-local-screenplay.json"; link.click(); URL.revokeObjectURL(url);
  };
  return <section className="screenplay-editor">
    <header className="screenplay-editor__header">
      <div><p className="eyebrow">{text("Writing room", "Sala de escritura")}</p><h2>{text("Screenplay", "Guion")}</h2></div>
      <div role="status">{saveState.saving ? text("Saving…", "Guardando…") : saveState.error ? text("Save paused", "Guardado en pausa") : saveState.dirty ? text("Unsaved changes", "Cambios sin guardar") : text("All changes saved", "Cambios guardados")}</div>
      <button className="button button--primary" disabled={freezing || importing || !!saveState.error} onClick={() => void saveRevision()}>{text("Save revision", "Guardar revisión")}</button>
    </header>
    {!!saveState.error && <div className="screenplay-editor__recovery" role="alert">
      <p>{conflict ? text("Another writer saved a newer draft. Your local text is preserved. Download it before loading their changes.", "Otra persona guardó un borrador más reciente. Tu texto local se conserva. Descárgalo antes de cargar los cambios.") : text("Could not save. Your text is preserved here.", "No se pudo guardar. Tu texto se conserva aquí.")}</p>
      <button className="button" onClick={downloadLocal}>{text("Download local copy", "Descargar copia local")}</button>
      {conflict ? <button className="button" onClick={() => { if (window.confirm(text("Replace this editor with the latest saved draft? Download your local copy first.", "¿Reemplazar el editor con el último borrador guardado? Descarga primero tu copia local."))) void getDraft(draft.project_id).then(onReload).catch(() => setNotice(text("Reload failed. Your text is still here.", "No se pudo recargar. Tu texto sigue aquí."))); }}>{text("Load latest draft", "Cargar último borrador")}</button> : <button className="button" onClick={() => void autosave.current?.retry().catch(() => undefined)}>{text("Retry save", "Reintentar guardado")}</button>}
    </div>}
    {notice && <p role="status">{notice}</p>}
    <div className="screenplay-editor__import">
      <label>{text("Import PDF, Word or Final Draft", "Importar PDF, Word o Final Draft")}<input type="file" accept=".pdf,.docx,.fdx" disabled={importing || !!saveState.error} onChange={event => { const file = event.target.files?.[0]; if (file) void importFile(file); event.target.value = ""; }} /></label>
      <p>{importing ? text("Importing screenplay…", "Importando guion…") : text("Review paragraph formatting after import. Originals remain in Documents.", "Revisa el formato tras importar. Los originales se conservan en Documentos.")}</p>
      <Link to={`/projects/${encodeURIComponent(draft.project_id)}/documents`}>{text("Documents", "Documentos")}</Link>
    </div>
    <div className="screenplay-editor__layout">
      <div>
        <div className="screenplay-editor__toolbar" role="group" aria-label={text("Paragraph format", "Formato de párrafo")}>
          {blockKinds.map((kind, index) => <button className="button" key={kind} onClick={() => editor?.chain().focus().updateAttributes("paragraph", { kind }).run()}>{text(["Scene", "Action", "Character", "Dialogue", "Parenthetical", "Transition"][index]!, ["Escena", "Acción", "Personaje", "Diálogo", "Acotación", "Transición"][index]!)}</button>)}
        </div>
        <EditorContent editor={editor} className="screenplay-editor__paper" />
      </div>
      <aside className="screenplay-editor__history" aria-label={text("Version history", "Historial de versiones")}>
        <h3>{text("Saved revisions", "Revisiones guardadas")}</h3>
        <p>{text("Revisions keep a fixed copy of your screenplay.", "Cada revisión conserva una copia fija del guion.")}</p>
        {revisions.length === 0 && <p>{text("Save your first revision when ready.", "Guarda la primera revisión cuando esté lista.")}</p>}
        {revisions.map(revision => <button className="button" key={revision.revision_id} onClick={() => void getRevision(draft.project_id, revision.revision_id).then(value => { if (alive.current) setPreview(value); }).catch(() => setNotice(text("Could not load revision.", "No se pudo cargar la revisión.")))}>{text("Revision", "Revisión")} {revision.draft_version} · {new Date(revision.created_at).toLocaleDateString()}</button>)}
        {more !== null && <button className="button" onClick={() => void listRevisions(draft.project_id, more).then(page => { if (alive.current) { setRevisions(items => [...items, ...page.revisions]); setMore(page.next_before_version); } }).catch(() => setNotice(text("Could not load more revisions.", "No se pudieron cargar más revisiones.")))}>{text("Load older revisions", "Cargar revisiones anteriores")}</button>}
        <Link to={`/projects/${encodeURIComponent(draft.project_id)}/script`}>{text("View analyzed screenplay", "Ver guion analizado")}</Link>
      </aside>
    </div>
    {preview && <section className="screenplay-editor__preview" aria-label={text("Revision preview", "Vista de revisión")}>
      <h3>{text("Revision", "Revisión")} {preview.draft_version}</h3>
      <button className="button" onClick={() => void downloadRevision(preview.revision_id, "pdf")}>{text("Download PDF", "Descargar PDF")}</button>
      <button className="button" onClick={() => void downloadRevision(preview.revision_id, "fdx")}>{text("Download Final Draft", "Descargar Final Draft")}</button>
      <button className="button" onClick={() => setPreview(null)}>{text("Close preview", "Cerrar vista")}</button>
      {preview.document?.content.map(block => <p key={block.attrs.blockId} id={block.attrs.kind === "scene-heading" ? `revision-scene-${block.attrs.sceneId}` : undefined} data-kind={block.attrs.kind}>{block.content?.map(node => node.text ?? "\n").join("")}</p>)}
    </section>}
  </section>;
}
