import {
  ExternalLink,
  FileText,
  FolderOpen,
  LayoutDashboard,
  MessageSquare,
} from "lucide-react";
import type { ReactElement } from "react";
import { NavLink } from "react-router";

import { API_DOCS_PATH } from "../api/client";

export interface SidebarProps {
  /** The open project, or null on routes outside one. */
  projectId: string | null;
  /** Called on every link click so a drawer can close itself. */
  onNavigate: () => void;
}

function linkClass({ isActive }: { isActive: boolean }): string {
  return isActive ? "sidebar__link sidebar__link--active" : "sidebar__link";
}

/**
 * Everything the sidebar holds, exhaustively: the brand, Projects, the
 * three project tabs while a project is open, and the API docs link. The
 * mockup's company selector, profile, team, settings, notifications,
 * search, reports, help and log out have no resource behind them and are
 * recorded in the Missing API registry instead of drawn.
 */
export function Sidebar({ projectId, onNavigate }: SidebarProps): ReactElement {
  const projectPath =
    projectId === null ? null : `/projects/${encodeURIComponent(projectId)}`;
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">ClearCut</div>
      <nav className="sidebar__nav" aria-label="Main">
        <NavLink to="/" end className={linkClass} onClick={onNavigate}>
          <FolderOpen aria-hidden="true" size={18} />
          Projects
        </NavLink>
        {projectPath !== null && (
          <>
            <NavLink to={projectPath} end className={linkClass} onClick={onNavigate}>
              <LayoutDashboard aria-hidden="true" size={18} />
              Overview
            </NavLink>
            <NavLink to={`${projectPath}/script`} className={linkClass} onClick={onNavigate}>
              <FileText aria-hidden="true" size={18} />
              Script
            </NavLink>
            <NavLink to={`${projectPath}/ask`} className={linkClass} onClick={onNavigate}>
              <MessageSquare aria-hidden="true" size={18} />
              Ask
            </NavLink>
          </>
        )}
      </nav>
      <footer className="sidebar__footer">
        <a className="sidebar__link" href={API_DOCS_PATH}>
          <ExternalLink aria-hidden="true" size={18} />
          API docs
        </a>
      </footer>
    </aside>
  );
}
