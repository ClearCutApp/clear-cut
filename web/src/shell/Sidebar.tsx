import {
  Building2,
  ExternalLink,
  FileChartColumn,
  FileText,
  Files,
  FolderOpen,
  LayoutDashboard,
  LifeBuoy,
  LogOut,
  MessageSquare,
  Settings,
  ShieldCheck,
  UserCheck,
  Users,
} from "lucide-react";
import type { ReactElement } from "react";
import { NavLink } from "react-router";

import { API_DOCS_PATH } from "../api/client";
import { UnavailableNav } from "./UnavailableNav";

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

const UNSERVED_MAIN = [
  { label: "Clearances", icon: <ShieldCheck aria-hidden="true" size={ICON_SIZE} /> },
  { label: "Documents", icon: <Files aria-hidden="true" size={ICON_SIZE} /> },
  { label: "Reports", icon: <FileChartColumn aria-hidden="true" size={ICON_SIZE} /> },
];

const ORGANIZATION = [
  { label: "Company & Profile", icon: <Building2 aria-hidden="true" size={ICON_SIZE} /> },
  { label: "Team & Roles", icon: <Users aria-hidden="true" size={ICON_SIZE} /> },
  { label: "Authorized Users", icon: <UserCheck aria-hidden="true" size={ICON_SIZE} /> },
  { label: "Settings", icon: <Settings aria-hidden="true" size={ICON_SIZE} /> },
];

const SUPPORT = [
  { label: "Help & Support", icon: <LifeBuoy aria-hidden="true" size={ICON_SIZE} /> },
  { label: "Log Out", icon: <LogOut aria-hidden="true" size={ICON_SIZE} /> },
];

/**
 * The design's whole sidebar, with each entry either wired or greyed.
 *
 * Wired: Projects, and -- while a project is open -- its Dashboard, Script
 * and Ask. Those are the four screens the API can answer.
 *
 * Greyed, with the reason beside them: Clearances, Documents and Reports;
 * the Organization group; Help and Log Out. There is no auth, no user, no
 * team, no document store and no report endpoint in the contract, so none
 * of them has anywhere to go. The company selector and the notification
 * count in the design are the same story and are handled in the top bar.
 */
export function Sidebar({ projectId, onNavigate }: SidebarProps): ReactElement {
  const projectPath =
    projectId === null ? null : `/projects/${encodeURIComponent(projectId)}`;
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">ClearCut</div>
      <nav className="sidebar__nav" aria-label="Main">
        <NavLink to="/" end className={linkClass} onClick={onNavigate}>
          <FolderOpen aria-hidden="true" size={ICON_SIZE} />
          Projects
        </NavLink>
        {projectPath !== null && (
          <>
            <NavLink to={projectPath} end className={linkClass} onClick={onNavigate}>
              <LayoutDashboard aria-hidden="true" size={ICON_SIZE} />
              Dashboard
            </NavLink>
            <NavLink to={`${projectPath}/script`} className={linkClass} onClick={onNavigate}>
              <FileText aria-hidden="true" size={ICON_SIZE} />
              Script
            </NavLink>
            <NavLink to={`${projectPath}/ask`} className={linkClass} onClick={onNavigate}>
              <MessageSquare aria-hidden="true" size={ICON_SIZE} />
              Ask
            </NavLink>
          </>
        )}
      </nav>
      {projectId === null && (
        <p className="sidebar__note">
          Dashboard, Script and Ask open once a project is open.
        </p>
      )}
      <UnavailableNav
        entries={UNSERVED_MAIN}
        reason="Clearances, documents and reports have no resource in the API: a clearance is the state of a tracker item, and nothing stores files or renders a report."
      />
      <UnavailableNav
        label="Organization"
        entries={ORGANIZATION}
        reason="The API has no accounts, no teams and no settings, so there is no company to show or membership to manage."
      />
      <footer className="sidebar__footer">
        <a className="sidebar__link" href={API_DOCS_PATH}>
          <ExternalLink aria-hidden="true" size={ICON_SIZE} />
          API docs
        </a>
        <UnavailableNav
          entries={SUPPORT}
          reason="There is no sign-in to leave and no support desk to reach: the API has no authentication."
        />
      </footer>
    </aside>
  );
}
