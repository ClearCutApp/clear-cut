import { useEffect, useState } from "react";
import { createOrganization, listOrganizations, type Organization } from "../../api/client";
import { useLocale } from "../../state/LocaleContext";

export function WorkspaceOnboarding({ onSelect }: { onSelect: (id: string) => void }) {
  const { text } = useLocale();
  const [organizations, setOrganizations] = useState<Organization[] | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState("");
  useEffect(() => {
    let active = true;
    listOrganizations().then((found) => {
      if (!active) return;
      setOrganizations(found);
      if (found[0]) { setSelected(found[0].organization_id);
      onSelect(found[0].organization_id); }
    }).catch(() => { if (active) setError(text("Workspaces could not be loaded. Reload to retry.", "No se pudieron cargar los espacios. Recarga para intentarlo de nuevo.")); });
    return () => { active = false; };
  }, [onSelect]);
  async function create() {
    setBusy(true);
      setError(null);
    try {
      const created = await createOrganization(name);
      setOrganizations((current) => [...(current ?? []), created]);
      setSelected(created.organization_id);
      onSelect(created.organization_id);
      setName("");
    } catch { setError(text("Workspace creation is unavailable. Try again.", "No se pudo crear el espacio. Inténtalo de nuevo.")); }
    finally { setBusy(false); }
  }
  return <section className="workspace-onboarding">
    <h2>{text("Workspace", "Espacio de trabajo")}</h2>
    {error && <p role="alert">{error}</p>}
    {organizations === null && !error && <p>{text("Loading workspaces…", "Cargando espacios…")}</p>}
    {organizations !== null && organizations.length > 0 && <label>{text("Create projects in", "Crear proyectos en")}
      <select value={selected} onChange={(event) => { setSelected(event.target.value);
      onSelect(event.target.value); }}>
        {organizations.map((org) => <option key={org.organization_id} value={org.organization_id}>{org.name}</option>)}
      </select>
      </label>}
    {organizations !== null && <form onSubmit={(event) => { event.preventDefault();
      void create(); }}>
      <label>{text("New workspace name", "Nombre del nuevo espacio")}<input required value={name} onChange={(event) => setName(event.target.value)} />
      </label>
      <button type="submit" className="landing-button" disabled={busy || !name.trim()}>{text("Create workspace", "Crear espacio")}</button>
    </form>}
  </section>;
}
