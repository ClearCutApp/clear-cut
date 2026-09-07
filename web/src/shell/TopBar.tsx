import { Menu, X } from "lucide-react";
import type { ReactElement } from "react";
import { useAuth } from "../state/AuthContext";
import { LanguageSwitch, useLocale } from "../state/LocaleContext";

export interface TopBarProps {
  drawerOpen: boolean;
  onToggleDrawer: () => void;
  drawerId: string;
}
export function TopBar({ drawerOpen, onToggleDrawer, drawerId }: TopBarProps): ReactElement {
  const Icon = drawerOpen ? X : Menu;
  const { user } = useAuth();
  const { text } = useLocale();
  return <header className="topbar">
    <button type="button" className="topbar__menu" aria-label={text("Menu", "Menú")}
      aria-expanded={drawerOpen} aria-controls={drawerId} onClick={onToggleDrawer}>
      <Icon aria-hidden="true" size={20} />
    </button>
      <span className="topbar__brand">ClearCut</span>
    <div className="topbar__tools">
      <LanguageSwitch />
      <span className="topbar__account" data-authenticated={!!user} title={user?.email ?? undefined}>{user?.email ?? text("Production workspace", "Espacio de producción")}</span>
      </div>
  </header>;
}
