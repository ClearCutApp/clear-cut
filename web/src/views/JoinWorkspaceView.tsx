import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router";
import { acceptWorkspaceInvitation } from "../api/client";
import { useAuth } from "../state/AuthContext";
import { useLocale } from "../state/LocaleContext";
import { useServerMode } from "../state/ServerModeContext";

export function JoinWorkspaceView() {
  const { text } = useLocale();
  const { user } = useAuth();
  const location = useLocation();
  const mode = useServerMode();
  const token = new URLSearchParams(location.hash.slice(1)).get("token") ?? "";
  const [busy, setBusy] = useState(false);
  const [joined, setJoined] = useState(false);
  const [error, setError] = useState(false);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const accept = async () => {
    setBusy(true); setError(false);
    try {
      await acceptWorkspaceInvitation(token);
      if (alive.current) {
        setJoined(true);
        window.history.replaceState(window.history.state, "", location.pathname);
      }
    } catch { if (alive.current) setError(true); }
    finally { if (alive.current) setBusy(false); }
  };
  return <section className="documents-view">
    <h1>{text("Join a workspace", "Unirse a un espacio")}</h1>
    {joined ? <><p>{text("You joined the workspace. A project manager must assign private projects separately.", "Te uniste al espacio. Una persona responsable debe asignarte los proyectos privados por separado.")}</p><Link to="/projects">{text("Open projects", "Abrir proyectos")}</Link></>
      : <><p>{user?.email}</p><p>{text("Accept using the verified email address named in the invitation.", "Acepta con la dirección de correo verificada indicada en la invitación.")}</p>
        <button className="button" disabled={busy || !token || mode === "mock"} onClick={() => void accept()}>{busy ? text("Joining…", "Uniéndote…") : text("Accept invitation", "Aceptar invitación")}</button></>}
    {!token && !joined && <p role="alert">{text("Open the complete invitation link.", "Abre el enlace completo de invitación.")}</p>}
    {error && <p role="alert">{text("Invitation unavailable. Check the account email, expiry, or ask the workspace owner for a new link.", "La invitación no está disponible. Revisa el correo de la cuenta, la caducidad o solicita otro enlace a la persona propietaria.")}</p>}
  </section>;
}
