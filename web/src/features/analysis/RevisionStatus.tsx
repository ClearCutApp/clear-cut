import { useEffect, useState } from "react";
import { useLocation } from "react-router";
import { getDraft, getProjectSettings } from "../../api/client";
import { useProject } from "../../state/ProjectContext";
import { useLocale } from "../../state/LocaleContext";

export function RevisionStatus() {
  const { analysis, projectId } = useProject();
  const { pathname } = useLocation();
  const { text } = useLocale();
  const [newerDraft, setNewerDraft] = useState(false);
  const [changedSettings, setChangedSettings] = useState(false);
  useEffect(() => {
    let current = true;
    setNewerDraft(false);
    setChangedSettings(false);
    if (analysis?.settings_version) {
      const version = analysis.settings_version;
      void getProjectSettings(projectId).then(settings => { if (current) setChangedSettings(settings.version > version); }).catch(() => {});
    }
    if (analysis?.revision_draft_version !== undefined) {
      const version = analysis.revision_draft_version;
      void getDraft(projectId).then(draft => { if (current) setNewerDraft(draft.version > version); }).catch(() => {});
    }
    return () => { current = false; };
  }, [analysis?.revision_draft_version, analysis?.settings_version, projectId, pathname]);
  if (!analysis?.revision_id || pathname.endsWith("/ask") || pathname.endsWith("/editor")) return null;
  return <p className="revision-status" role="status">
    {text("Results for saved revision", "Resultados de la revisión guardada")} {analysis.revision_draft_version}.
    {newerDraft && <> {text("The draft has changed. These findings describe the earlier revision.", "El borrador ha cambiado. Estos hallazgos describen la revisión anterior.")}</>}
    {changedSettings && <> {text("Production settings changed since this analysis. Review the current locations before relying on these results.", "La configuración de producción cambió después del análisis. Revisa las ubicaciones actuales antes de usar estos resultados.")}</>}
    {!!analysis.coverage_gaps?.length && <> {text("Some research has no verified cited evidence.", "Parte de la investigación no tiene evidencia citada verificada.")}</>}
  </p>;
}
