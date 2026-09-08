import {
  Activity,
  Bell,
  Building2,
  ChartColumn,
  CircleQuestionMark,
  Clapperboard,
  ExternalLink,
  FileChartColumn,
  FileText,
  Files,
  Gauge,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  PenLine,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  UserCheck,
  Users,
} from "lucide-react";
import { useEffect, useState, type ReactElement } from "react";
import { NavLink } from "react-router";

import { logOut, useAuth } from "../state/AuthContext";
import { useLocale } from "../state/LocaleContext";
import { API_DOCS_PATH, listOrganizations, type Organization } from "../api/client";
import { UnavailableNav } from "./UnavailableNav";

export interface SidebarProps {
  /** The open project, or null on routes outside one. */
  projectId: string | null;
  /** Called on every link click so a drawer can close itself. */
  onNavigate: () => void;
}

const ICON_SIZE = 18;

/**
 * The avatar tones, in the order the hash steps through them. Red is not in
 * the set: in this palette red means risk, error and blocked, and a
 * workspace is none of those.
 */
const AVATAR_TONES = ["green", "amber", "blue"] as const;

function linkClass({ isActive }: { isActive: boolean }): string {
  return isActive ? "sidebar__link sidebar__link--active" : "sidebar__link";
}

/**
 * The initials the workspace avatar draws. `Organization` carries no avatar
 * image field, so the name is the only thing there is to draw from; two
 * letters is what fits the circle.
 */
export function workspaceInitials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) {
    return "?";
  }
  return words
    .slice(0, 2)
    .map((word) => word.slice(0, 1).toUpperCase())
    .join("");
}

/**
 * One of the three tones, chosen by the organization id. A sum of code
 * points is enough: it is stable across renders, reloads and machines,
 * which is the whole requirement, and no one has to read it.
 */
export function workspaceTone(organizationId: string): string {
  let sum = 0;
  for (const character of organizationId) {
    sum += character.codePointAt(0) ?? 0;
  }
  return AVATAR_TONES[sum % AVATAR_TONES.length];
}

/**
 * The role the API returns, in words. The wire values are role names rather
 * than copy, so they are mapped here instead of being printed raw; an
 * unknown role prints as it arrived rather than disappearing.
 */
function roleLabel(role: string, text: (en: string, es: string) => string): string {
  switch (role) {
    case "owner":
      return text("Owner", "Propietario");
    case "admin":
      return text("Administrator", "Administrador");
    case "producer":
      return text("Producer", "Productor");
    case "writer":
      return text("Writer", "Guionista");
    case "viewer":
      return text("Viewer", "Lector");
    default:
      return role;
  }
}

/**
 * Project navigation: the workspace the person is signed in to, the
 * destinations this API serves, the ones the design draws that it does not,
 * and the identity actions.
 */
export function Sidebar({ projectId, onNavigate }: SidebarProps): ReactElement {
  const { user } = useAuth();
  const { text } = useLocale();
  const [organizations, setOrganizations] = useState<Organization[]>([]);

  // A failed load leaves the list empty, which renders no workspace block at
  // all: an empty avatar and a blank name would be a worse answer than
  // silence, and the nav below must come up either way.
  useEffect(() => {
    if (!user) {
      return undefined;
    }
    let active = true;
    void listOrganizations()
      .then((values) => {
        if (active) {
          setOrganizations(values);
        }
      })
      .catch(() => {
        if (active) {
          setOrganizations([]);
        }
      });
    return () => {
      active = false;
    };
  }, [user]);

  const workspace = organizations[0] ?? null;
  const projectPath =
    projectId === null ? null : `/projects/${encodeURIComponent(projectId)}`;

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">ClearCut</div>

      {/* The design puts a chevron here that opens a workspace switcher.
          There is no active-organization state in this app -- nothing the
          switch could change -- so the block is drawn in its single
          workspace form, without a control. A chevron that reordered
          nothing would be the same lie `UnavailableNav` exists to avoid.
          When an active workspace becomes real state, the chevron and the
          list belong here. Until then the one place that does pick a
          workspace is Team & Roles, and the line below says so. */}
      {workspace !== null && (
        <div className="sidebar__workspace">
          <span
            className={`sidebar__workspace-avatar sidebar__workspace-avatar--${workspaceTone(workspace.organization_id)}`}
            aria-hidden="true"
          >
            {workspaceInitials(workspace.name)}
          </span>
          <span className="sidebar__workspace-text">
            <span className="sidebar__workspace-name">{workspace.name}</span>
            <span className="sidebar__workspace-role">
              {roleLabel(workspace.role, text)}
            </span>
          </span>
        </div>
      )}
      {organizations.length > 1 && (
        <p className="sidebar__note">
          {text(
            "You belong to more than one workspace. Team & Roles is where one is chosen.",
            "Perteneces a más de un espacio de trabajo. Puedes elegir uno en Equipo y roles.",
          )}
        </p>
      )}

      <nav className="sidebar__nav" aria-label="Main">
        <NavLink to="/projects" end className={linkClass} onClick={onNavigate}>
          <Clapperboard aria-hidden="true" size={ICON_SIZE} />
          {text("Projects", "Proyectos")}
        </NavLink>
      </nav>
      <UnavailableNav
        entries={[
          {
            label: text("Dashboard", "Panel"),
            icon: <LayoutDashboard aria-hidden="true" size={ICON_SIZE} />,
          },
          {
            label: text("Clearances", "Autorizaciones"),
            icon: <ShieldCheck aria-hidden="true" size={ICON_SIZE} />,
          },
          {
            label: text("Reports", "Informes"),
            icon: <ChartColumn aria-hidden="true" size={ICON_SIZE} />,
          },
        ]}
        reason={text(
          "Clearances and reports are read one project at a time, and there is no cross-project dashboard behind them yet.",
          "Las autorizaciones y los informes se consultan proyecto por proyecto, y todavía no hay un panel que los reúna.",
        )}
      />

      {/* The design moves these into tabs across the top of the project
          page. Those tabs do not exist yet, and dropping the links before
          they do would strand every route under `/projects/:id`. They move
          under the tabs when the tabs land. The group is labelled generically
          because the sidebar sits outside `ProjectLayout` and so never has
          the project's title -- only its id, which is not a name. */}
      {projectPath !== null && (
        <div className="sidebar__group">
          <p className="sidebar__group-label">{text("Project", "Proyecto")}</p>
          <nav className="sidebar__nav" aria-label={text("Project", "Proyecto")}>
            <NavLink to={projectPath} end className={linkClass} onClick={onNavigate}>
              <Gauge aria-hidden="true" size={ICON_SIZE} />
              {text("Overview", "Resumen")}
            </NavLink>
            <NavLink to={`${projectPath}/editor`} className={linkClass} onClick={onNavigate}>
              <PenLine aria-hidden="true" size={ICON_SIZE} />
              {text("Write", "Escribir")}
            </NavLink>
            <NavLink to={`${projectPath}/script`} className={linkClass} onClick={onNavigate}>
              <FileText aria-hidden="true" size={ICON_SIZE} />
              {text("Script", "Guion")}
            </NavLink>
            <NavLink to={`${projectPath}/documents`} className={linkClass} onClick={onNavigate}>
              <Files aria-hidden="true" size={ICON_SIZE} />
              {text("Documents", "Documentos")}
            </NavLink>
            <NavLink to={`${projectPath}/ask`} className={linkClass} onClick={onNavigate}>
              <MessageSquare aria-hidden="true" size={ICON_SIZE} />
              {text("Ask", "Preguntar")}
            </NavLink>
            <NavLink to={`${projectPath}/reports`} className={linkClass} onClick={onNavigate}>
              <FileChartColumn aria-hidden="true" size={ICON_SIZE} />
              {text("Reports", "Informes")}
            </NavLink>
            <NavLink to={`${projectPath}/search`} className={linkClass} onClick={onNavigate}>
              <Search aria-hidden="true" size={ICON_SIZE} />
              {text("Search", "Buscar")}
            </NavLink>
            <NavLink to={`${projectPath}/notifications`} className={linkClass} onClick={onNavigate}>
              <Bell aria-hidden="true" size={ICON_SIZE} />
              {text("Notifications", "Notificaciones")}
            </NavLink>
            <NavLink to={`${projectPath}/activity`} className={linkClass} onClick={onNavigate}>
              <Activity aria-hidden="true" size={ICON_SIZE} />
              {text("Activity", "Actividad")}
            </NavLink>
            <NavLink to={`${projectPath}/settings`} className={linkClass} onClick={onNavigate}>
              <SlidersHorizontal aria-hidden="true" size={ICON_SIZE} />
              {text("Production", "Producción")}
            </NavLink>
          </nav>
        </div>
      )}

      {/* The design orders this group Company & Profile, Team & Roles,
          Authorized Users, Settings. The one entry with a route is lifted to
          the top instead, because `UnavailableNav` carries one reason for
          the entries under it, and splitting the group around the live link
          would print that reason twice. */}
      {user && (
        <div className="sidebar__group">
          <p className="sidebar__group-label">{text("Organization", "Organización")}</p>
          <nav className="sidebar__nav" aria-label={text("Organization", "Organización")}>
            <NavLink to="/team" className={linkClass} onClick={onNavigate}>
              <Users aria-hidden="true" size={ICON_SIZE} />
              {text("Team & Roles", "Equipo y roles")}
            </NavLink>
          </nav>
          <UnavailableNav
            entries={[
              {
                label: text("Company & Profile", "Empresa y perfil"),
                icon: <Building2 aria-hidden="true" size={ICON_SIZE} />,
              },
              {
                label: text("Authorized Users", "Usuarios autorizados"),
                icon: <UserCheck aria-hidden="true" size={ICON_SIZE} />,
              },
              {
                label: text("Settings", "Ajustes"),
                icon: <Settings aria-hidden="true" size={ICON_SIZE} />,
              },
            ]}
            reason={text(
              "The API exposes an organization's members and nothing else about it: no company profile, no authorized-user list and no workspace settings.",
              "La API solo expone los miembros de una organización: no hay perfil de empresa, ni lista de usuarios autorizados, ni ajustes del espacio de trabajo.",
            )}
          />
        </div>
      )}

      <footer className="sidebar__footer">
        <UnavailableNav
          entries={[
            {
              label: text("Help & Support", "Ayuda y soporte"),
              icon: <CircleQuestionMark aria-hidden="true" size={ICON_SIZE} />,
            },
          ]}
          reason={text(
            "There is no support desk behind this build. The API reference below is the documentation that exists.",
            "Esta versión no tiene servicio de soporte. La referencia de la API que aparece debajo es la documentación disponible.",
          )}
        />
        <a className="sidebar__link" href={API_DOCS_PATH}>
          <ExternalLink aria-hidden="true" size={ICON_SIZE} />
          {text("API docs", "Documentación de la API")}
        </a>
        {user && (
          <button
            type="button"
            className="sidebar__link sidebar__link--danger"
            onClick={() => void logOut()}
          >
            <LogOut aria-hidden="true" size={ICON_SIZE} />
            {text("Log Out", "Cerrar sesión")}
          </button>
        )}
      </footer>
    </aside>
  );
}
