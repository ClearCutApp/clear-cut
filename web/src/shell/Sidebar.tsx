import {
  ExternalLink,
  FileText,
  FolderOpen,
  LayoutDashboard,
  LogOut,
  MessageSquare,
} from "lucide-react";
import type { ReactElement } from "react";
import { NavLink } from "react-router";

import { logOut, useAuth } from "../state/AuthContext";
import { useLocale } from "../state/LocaleContext";
import { API_DOCS_PATH } from "../api/client";

export interface SidebarProps {
  /** The open project, or null on routes outside one. */
  projectId: string | null;
  /** Called on every link click so a drawer can close itself. */
  onNavigate: () => void;
}

const ICON_SIZE = 18;

function linkClass({ isActive }: { isActive: boolean }): string {
  return isActive ? "sidebar__link sidebar__link--active" : "sidebar__link";
}

/** Project navigation exposes working destinations and identity actions. */
export function Sidebar({ projectId, onNavigate }: SidebarProps): ReactElement {
  const { user } = useAuth();
  const { text } = useLocale();
  const projectPath =
    projectId === null ? null : `/projects/${encodeURIComponent(projectId)}`;
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">ClearCut</div>
      <nav className="sidebar__nav" aria-label="Main">
        <NavLink to="/projects" end className={linkClass} onClick={onNavigate}>
          <FolderOpen aria-hidden="true" size={ICON_SIZE} />
          {text("Projects", "Proyectos")}
        </NavLink>
        {user && <NavLink to="/team" className={linkClass} onClick={onNavigate}>
          <FolderOpen aria-hidden="true" size={ICON_SIZE} />{text("Team", "Equipo")}
        </NavLink>}
        {projectPath !== null && (
          <>
            <NavLink to={projectPath} end className={linkClass} onClick={onNavigate}>
              <LayoutDashboard aria-hidden="true" size={ICON_SIZE} />
              {text("Overview", "Resumen")}
            </NavLink>
            <NavLink to={`${projectPath}/editor`} className={linkClass} onClick={onNavigate}>
              <FileText aria-hidden="true" size={ICON_SIZE} />{text("Write", "Escribir")}
            </NavLink>
            <NavLink to={`${projectPath}/script`} className={linkClass} onClick={onNavigate}>
              <FileText aria-hidden="true" size={ICON_SIZE} />
              {text("Script", "Guion")}
            </NavLink>
            <NavLink to={`${projectPath}/documents`} className={linkClass} onClick={onNavigate}>
              <FileText aria-hidden="true" size={ICON_SIZE} />{text("Documents", "Documentos")}
            </NavLink>
            <NavLink to={`${projectPath}/ask`} className={linkClass} onClick={onNavigate}>
              <MessageSquare aria-hidden="true" size={ICON_SIZE} />
              {text("Ask", "Preguntar")}
            </NavLink>
            <NavLink to={`${projectPath}/reports`} className={linkClass} onClick={onNavigate}>
              <FileText aria-hidden="true" size={ICON_SIZE} />{text("Reports", "Informes")}
            </NavLink>
            <NavLink to={`${projectPath}/search`} className={linkClass} onClick={onNavigate}>
              <LayoutDashboard aria-hidden="true" size={ICON_SIZE} />{text("Search", "Buscar")}
            </NavLink>
            <NavLink to={`${projectPath}/notifications`} className={linkClass} onClick={onNavigate}>
              <LayoutDashboard aria-hidden="true" size={ICON_SIZE} />{text("Notifications", "Notificaciones")}
            </NavLink>
            <NavLink to={`${projectPath}/activity`} className={linkClass} onClick={onNavigate}>
              <LayoutDashboard aria-hidden="true" size={ICON_SIZE} />{text("Activity", "Actividad")}
            </NavLink>
            <NavLink to={`${projectPath}/settings`} className={linkClass} onClick={onNavigate}>
              <FolderOpen aria-hidden="true" size={ICON_SIZE} />{text("Production", "Producción")}
            </NavLink>
          </>
        )}
      </nav>
      {projectId === null && (
        <p className="sidebar__note">
          Dashboard, Script and Ask open once a project is open.
        </p>
      )}
      <footer className="sidebar__footer">
        <a className="sidebar__link" href={API_DOCS_PATH}>
          <ExternalLink aria-hidden="true" size={ICON_SIZE} />
          API docs
        </a>
        {user && <button type="button" className="sidebar__link" onClick={() => void logOut()}>
          <LogOut aria-hidden="true" size={ICON_SIZE} />{text("Sign out", "Cerrar sesión")}
        </button>}
      </footer>
    </aside>
  );
}
