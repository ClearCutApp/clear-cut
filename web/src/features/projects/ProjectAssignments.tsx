import { useEffect, useRef, useState } from "react";
import { assignProjectMember, getProjectMembers, getWorkspaceMembers,
  type ProjectMembers, type WorkspaceMember, type WorkspaceRole } from "../../api/client";
import { useLocale } from "../../state/LocaleContext";

export function ProjectAssignments({ projectId }: { projectId: string }) {
  const { text } = useLocale();
  const [access, setAccess] = useState<ProjectMembers | null>(null);
  const [directory, setDirectory] = useState<WorkspaceMember[]>([]);
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<WorkspaceRole>("writer");
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const scope = useRef<object>({});
  useEffect(() => {
    const current = {}; scope.current = current;
    setAccess(null); setDirectory([]); setUserId(""); setError(false);
    void getProjectMembers(projectId).then(async value => {
      if (scope.current !== current) return;
      setAccess(value);
      if (value.can_manage) {
        const people = await getWorkspaceMembers(value.organization_id);
        if (scope.current === current) setDirectory(people.members.filter(member => member.active));
      }
    }).catch(() => { if (scope.current === current) setError(true); });
    return () => { scope.current = {}; };
  }, [projectId, refresh]);
  const save = async (target: string, grant: WorkspaceRole | null) => {
    if (!access) return;
    const current = scope.current; setBusy(true); setError(false);
    try {
      await assignProjectMember(projectId, target, grant, access.version);
      if (scope.current === current) setRefresh(value => value + 1);
    } catch { if (scope.current === current) setError(true); }
    finally { if (scope.current === current) setBusy(false); }
  };
  return <section>
    <h2>{text("Private project access", "Acceso al proyecto privado")}</h2>
    <p>{text("Only explicitly assigned members can open this project.", "Solo las personas asignadas expresamente pueden abrir este proyecto.")}</p>
    {access?.can_manage && <form onSubmit={event => { event.preventDefault(); void save(userId, role); }}>
      <label>{text("Workspace member", "Miembro del espacio")}<select required value={userId} onChange={event => setUserId(event.target.value)}><option value="">{text("Choose a member", "Elige una persona")}</option>{directory.map(member => <option key={member.user_id} value={member.user_id}>{member.email || member.user_id}</option>)}</select></label>
      <label>{text("Project role", "Rol del proyecto")}<select value={role} onChange={event => setRole(event.target.value as WorkspaceRole)}>{["admin", "producer", "writer", "viewer"].map(value => <option key={value}>{value}</option>)}</select></label>
      <button className="button" disabled={!userId || busy}>{text("Save assignment", "Guardar asignación")}</button>
    </form>}
    <ul className="documents-view__list">{access?.members.map(member => <li key={member.user_id}><div><strong>{member.email || member.user_id}</strong><p>{member.role}</p></div>{access.can_manage && <button className="button" disabled={busy} onClick={() => void save(member.user_id, null)}>{text("Remove from project", "Retirar del proyecto")}</button>}</li>)}</ul>
    {error && <p role="alert">{text("Project access could not be loaded or changed. Reload and check permissions.", "No se pudo cargar o cambiar el acceso. Recarga y revisa los permisos.")}</p>}
    <button className="button" disabled={busy} onClick={() => setRefresh(value => value + 1)}>{text("Reload assignments", "Recargar asignaciones")}</button>
  </section>;
}
