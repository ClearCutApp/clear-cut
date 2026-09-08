import { useEffect, useRef, useState } from "react";
import { ApiError, getProjectMembers, getProjectSettings, saveProjectSettings,
  type ProjectSettings } from "../api/client";
import { LocalResearchPanel } from "../features/projects/LocalResearchPanel";
import { ProjectAssignments } from "../features/projects/ProjectAssignments";
import { useLocale } from "../state/LocaleContext";
import { useProject } from "../state/ProjectContext";
import { useServerMode } from "../state/ServerModeContext";
import { jurisdictionName, LAUNCH_COUNTRIES } from "../theme/jurisdictions";

export function ProjectSettingsView() {
  const project = useProject();
  const { projectId } = project;
  const { text, locale } = useLocale();
  const mode = useServerMode();
  const [settings, setSettings] = useState<ProjectSettings | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [editable, setEditable] = useState(false);
  const scope = useRef<object>({});
  useEffect(() => {
    const current = {}; scope.current = current;
    setSettings(null); setError(null); setMessage(null); setBusy(false); setEditable(false);
    if (mode === "mock") return;
    void Promise.all([getProjectSettings(projectId), getProjectMembers(projectId)]).then(([value, access]) => { if (scope.current === current) { setSettings(value); setEditable(access.can_edit === true); } })
      .catch(() => { if (scope.current === current) setError(text("Could not load settings.", "No se pudo cargar la configuración.")); });
    return () => { scope.current = {}; };
  }, [projectId, refresh, mode, text]);
  const save = async () => {
    if (!settings) return;
    const current = scope.current; setBusy(true); setError(null); setMessage(null);
    try {
      const saved = await saveProjectSettings(projectId, settings);
      if (scope.current !== current) return;
      setSettings(saved);
      setMessage(text("Settings saved. Analyze a saved revision to assess the current production locations. National sources do not establish local permits.", "Configuración guardada. Analiza una revisión guardada para evaluar las ubicaciones actuales. Las fuentes nacionales no determinan los permisos locales."));
      await project.refreshMetadata?.();
    } catch (cause) {
      if (scope.current === current) setError(cause instanceof ApiError && cause.status === 409
        ? text("Settings changed elsewhere. Your edits are preserved; copy them before reloading.", "La configuración cambió en otra sesión. Tus ediciones se conservan; cópialas antes de recargar.")
        : text("Could not save settings. Your edits are preserved.", "No se pudo guardar. Tus ediciones se conservan."));
    } finally { if (scope.current === current) setBusy(false); }
  };
  return <section className="documents-view">
    <h1>{text("Production settings", "Configuración de producción")}</h1>
    {mode === "mock" ? <p>{text("Production settings and team assignments require a configured account.", "La configuración de producción y las asignaciones requieren una cuenta configurada.")}</p> : <>
      {settings && <form onSubmit={event => { event.preventDefault(); void save(); }}>
        <fieldset disabled={busy || !editable}>
          <label>{text("Project title", "Título del proyecto")}<input required maxLength={200} value={settings.title} onChange={event => setSettings({ ...settings, title: event.target.value })} /></label>
          <label>{text("Primary jurisdiction", "Jurisdicción principal")}<select value={settings.jurisdiction_code} onChange={event => setSettings({ ...settings, jurisdiction_code: event.target.value })}>{!(LAUNCH_COUNTRIES as readonly string[]).includes(settings.jurisdiction_code) && <option value={settings.jurisdiction_code}>{text("Outside launch coverage", "Fuera de cobertura inicial")}</option>}{LAUNCH_COUNTRIES.map(code => <option key={code} value={code}>{jurisdictionName(code, locale)}</option>)}</select></label>
          <h2>{text("Production locations", "Ubicaciones de producción")}</h2>
          <p>{text("Record cities, regions, addresses or descriptive filming locations. Missing local research remains an explicit coverage gap.", "Registra ciudades, regiones, direcciones o descripciones de lugares de rodaje. La investigación local pendiente sigue siendo una laguna de cobertura explícita.")}</p>
          {settings.locations.map((location, index) => <div key={index} className="field">
            <label>{text("Country", "País")}<select value={location.country} onChange={event => setSettings({ ...settings, locations: settings.locations.map((value, i) => i === index ? { ...value, country: event.target.value } : value) })}>{LAUNCH_COUNTRIES.map(code => <option key={code} value={code}>{jurisdictionName(code, locale)}</option>)}</select></label>
            <label>{text("Location", "Ubicación")}<input required maxLength={500} value={location.location} onChange={event => setSettings({ ...settings, locations: settings.locations.map((value, i) => i === index ? { ...value, location: event.target.value } : value) })} /></label>
            <button type="button" className="button" onClick={() => setSettings({ ...settings, locations: settings.locations.filter((_, i) => i !== index) })}>{text("Remove location", "Quitar ubicación")}</button>
          </div>)}
          <button type="button" className="button" disabled={settings.locations.length >= 30} onClick={() => setSettings({ ...settings, locations: [...settings.locations, { country: settings.jurisdiction_code, location: "" }] })}>{text("Add location", "Añadir ubicación")}</button>
          <button className="button button--primary">{text("Save production settings", "Guardar configuración de producción")}</button>
        </fieldset>
      </form>}
      {settings && !editable && <p>{text("A producer or project administrator can edit these settings.", "Una persona productora o administradora del proyecto puede editar esta configuración.")}</p>}
      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
      <button className="button" disabled={busy} onClick={() => setRefresh(value => value + 1)}>{text("Reload saved settings", "Recargar configuración guardada")}</button>
      {settings && <LocalResearchPanel projectId={projectId} savedVersion={settings.version} editable={editable} />}
      <ProjectAssignments projectId={projectId} />
    </>}
  </section>;
}
