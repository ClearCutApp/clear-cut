import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { changeWorkspaceMember, getWorkspaceInvitations, getWorkspaceMembers, inviteWorkspaceMember,
  listOrganizations, revokeWorkspaceInvitation, type Organization, type WorkspaceInvitation,
  type WorkspaceMember, type WorkspaceRole } from "../api/client";
import { useAuth } from "../state/AuthContext";
import { useLocale } from "../state/LocaleContext";
import { useServerMode } from "../state/ServerModeContext";

const roles: WorkspaceRole[] = ["admin", "producer", "writer", "viewer"];

function MemberRow({ member, owner, onChange, busy }: {
  member: WorkspaceMember; owner: boolean; busy: boolean;
  onChange: (member: WorkspaceMember, role: WorkspaceRole, active: boolean) => void;
}) {
  const { text } = useLocale();
  const { user } = useAuth();
  const [role, setRole] = useState(member.role);
  const [removing, setRemoving] = useState(false);
  const label = member.user_id === user?.uid ? text("You", "Tú") : member.email || member.user_id;
  const editable = member.active && (owner || member.role !== "owner");
  return <li><div><strong>{label}</strong><p>{member.active ? text("Active member", "Miembro activo") : text("Access revoked", "Acceso revocado")}</p></div>
    {editable && <><label>{text("Role", "Rol")}<select aria-label={text("Role for ", "Rol de ") + label} value={role} disabled={busy} onChange={event => setRole(event.target.value as WorkspaceRole)}>
      {(owner ? ["owner", ...roles] : roles).map(value => <option key={value} value={value}>{value}</option>)}
    </select></label><button className="button" disabled={busy || role === member.role} onClick={() => onChange(member, role, true)}>{text("Save role", "Guardar rol")}</button>
    {!removing ? <button className="button" disabled={busy} onClick={() => setRemoving(true)}>{text("Remove access", "Retirar acceso")}</button>
      : <span>{text("Rejoining will require a new invitation and project assignments.", "Para volver, se necesitarán otra invitación y nuevas asignaciones de proyectos.")}<button className="button" disabled={busy} onClick={() => onChange(member, member.role, false)}>{text("Confirm removal", "Confirmar retirada")}</button><button className="button" onClick={() => setRemoving(false)}>{text("Cancel", "Cancelar")}</button></span>}</>}
  </li>;
}

export function TeamView() {
  const { text } = useLocale();
  const mode = useServerMode();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organization, setOrganization] = useState("");
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [invitations, setInvitations] = useState<WorkspaceInvitation[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<WorkspaceRole>("writer");
  const [link, setLink] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const scope = useRef<object>({});
  useEffect(() => {
    let active = true;
    if (mode === "mock") return;
    void listOrganizations().then(values => {
      if (!active) return;
      setOrganizations(values.filter(value => ["owner", "admin"].includes(value.role)));
      setOrganization(values.find(value => ["owner", "admin"].includes(value.role))?.organization_id ?? "");
    }).catch(() => { if (active) setError(text("Could not load workspaces.", "No se pudieron cargar los espacios.")); });
    return () => { active = false; };
  }, [mode, text]);
  useEffect(() => {
    const current = {}; scope.current = current;
    setMembers([]); setInvitations([]); setLink(""); setError(null);
    if (!organization) return;
    setBusy(true);
    void Promise.all([getWorkspaceMembers(organization), getWorkspaceInvitations(organization)])
      .then(([people, invites]) => { if (scope.current === current) { setMembers(people.members); setInvitations(invites.invitations); } })
      .catch(() => { if (scope.current === current) setError(text("Team access is unavailable. Check your workspace permissions.", "El equipo no está disponible. Revisa tus permisos.")); })
      .finally(() => { if (scope.current === current) setBusy(false); });
    return () => { scope.current = {}; };
  }, [organization, refresh, text]);
  const mutate = async (operation: Promise<unknown>) => {
    const current = scope.current; setBusy(true); setError(null);
    try { await operation; if (scope.current === current) setRefresh(value => value + 1); }
    catch { if (scope.current === current) setError(text("Change was not saved. Reload the team and check permissions or ownership before retrying.", "No se guardó el cambio. Recarga el equipo y revisa los permisos o la titularidad antes de reintentar.")); }
    finally { if (scope.current === current) setBusy(false); }
  };
  const invite = async () => {
    const current = scope.current; setBusy(true); setError(null); setLink("");
    try {
      const created = await inviteWorkspaceMember(organization, email, role);
      if (scope.current !== current) return;
      setInvitations(values => [created.invitation, ...values]);
      setLink(window.location.origin + "/join#token=" + encodeURIComponent(created.token));
      setEmail("");
    } catch { if (scope.current === current) setError(text("Could not create the invitation.", "No se pudo crear la invitación.")); }
    finally { if (scope.current === current) setBusy(false); }
  };
  return <section className="documents-view">
    <h1>{text("Team settings", "Configuración del equipo")}</h1>
    <p>{text("Workspace membership does not expose private projects. Assign each project separately.", "Pertenecer al espacio no da acceso a los proyectos privados. Cada proyecto se asigna por separado.")}</p>
    {mode === "mock" ? <p>{text("Team management requires a configured account.", "La gestión de equipos requiere una cuenta configurada.")}</p> : <>
      {organizations.length === 0 && <p>{text("An owner or administrator can manage the team.", "Una persona propietaria o administradora puede gestionar el equipo.")} <Link to="/projects">{text("Projects", "Proyectos")}</Link></p>}
      {organizations.length > 0 && <label>{text("Workspace", "Espacio")}<select value={organization} onChange={event => setOrganization(event.target.value)}>{organizations.map(value => <option key={value.organization_id} value={value.organization_id}>{value.name}</option>)}</select></label>}
      {organization && <>
        <form onSubmit={event => { event.preventDefault(); void invite(); }}>
          <h2>{text("Invite a collaborator", "Invitar a una persona")}</h2>
          <label>{text("Verified account email", "Correo de la cuenta verificada")}<input type="email" required maxLength={254} value={email} onChange={event => setEmail(event.target.value)} /></label>
          <label>{text("Workspace role", "Rol del espacio")}<select value={role} onChange={event => setRole(event.target.value as WorkspaceRole)}>{roles.map(value => <option key={value}>{value}</option>)}</select></label>
          <button className="button" disabled={busy || !email}>{text("Create invitation link", "Crear enlace de invitación")}</button>
        </form>
        {link && <div role="status"><p>{text("Share this private link with the invited email holder. It expires in seven days; no message has been sent.", "Comparte este enlace privado con la persona invitada. Caduca en siete días; no se ha enviado ningún mensaje.")}</p><input aria-label={text("Invitation link", "Enlace de invitación")} readOnly value={link} onFocus={event => event.target.select()} /></div>}
        <h2>{text("Members", "Miembros")}</h2>
        <ul className="documents-view__list">{members.map(member => <MemberRow key={member.user_id + ":" + member.version} member={member} busy={busy} owner={organizations.find(value => value.organization_id === organization)?.role === "owner"} onChange={(member, role, active) => void mutate(changeWorkspaceMember(organization, member, role, active))} />)}</ul>
        <h2>{text("Invitations", "Invitaciones")}</h2>
        <ul className="documents-view__list">{invitations.map(invitation => <li key={invitation.invitation_id}><div><strong>{invitation.email}</strong><p>{invitation.state} · {new Date(invitation.expires_at).toLocaleDateString()}</p></div>{invitation.state === "pending" && <button className="button" disabled={busy} onClick={() => void mutate(revokeWorkspaceInvitation(organization, invitation))}>{text("Revoke", "Revocar")}</button>}</li>)}</ul>
        <button className="button" disabled={busy} onClick={() => setRefresh(value => value + 1)}>{text("Reload team", "Recargar equipo")}</button>
      </>}
    </>}
    {busy && <p role="status">{text("Updating team…", "Actualizando equipo…")}</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
