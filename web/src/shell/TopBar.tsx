import { Bell, Menu, Search, UserRound, X } from "lucide-react";
import type { ReactElement } from "react";

export interface TopBarProps {
  drawerOpen: boolean;
  onToggleDrawer: () => void;
  /** The element the menu button controls, for `aria-controls`. */
  drawerId: string;
}

const TOOLS = [
  { label: "Search ClearCut & the web", icon: <Search aria-hidden="true" size={16} /> },
  { label: "Notifications", icon: <Bell aria-hidden="true" size={16} /> },
  { label: "Account", icon: <UserRound aria-hidden="true" size={16} /> },
];

/**
 * The bar across the top of every screen: the drawer toggle (below the wide
 * breakpoint), the brand, and the three global affordances the design puts
 * on the right.
 *
 * All three are drawn greyed. There is no search endpoint, no notification
 * feed and no signed-in user in the contract, so a real search box would
 * take a query nothing can answer, a bell would need a count to invent, and
 * an account chip would need a name and a face this app does not have. They
 * are shown rather than dropped because a reader who knows the design would
 * otherwise go looking for them.
 */
export function TopBar({
  drawerOpen,
  onToggleDrawer,
  drawerId,
}: TopBarProps): ReactElement {
  const MenuIcon = drawerOpen ? X : Menu;
  return (
    <header className="topbar">
      <button
        type="button"
        className="topbar__menu"
        aria-label="Menu"
        aria-expanded={drawerOpen}
        aria-controls={drawerId}
        onClick={onToggleDrawer}
      >
        <MenuIcon aria-hidden="true" size={20} />
      </button>
      <span className="topbar__brand">ClearCut</span>
      <div className="topbar__tools">
        <ul className="topbar__tool-list">
          {TOOLS.map((tool) => (
            <li key={tool.label} className="topbar__tool" aria-disabled="true">
              {tool.icon}
              <span className="topbar__tool-label">{tool.label}</span>
            </li>
          ))}
        </ul>
        <p className="topbar__note">
          Search, notifications and the account menu are drawn from resources
          this API does not have.
        </p>
      </div>
    </header>
  );
}
