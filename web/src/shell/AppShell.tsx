import { useEffect, useRef, useState, type ReactElement } from "react";
import { Outlet, useMatch } from "react-router";

import { ModeBanner } from "../components/atoms/ModeBanner";
import { useServerMode } from "../state/ServerModeContext";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

const DRAWER_ID = "shell-drawer";

/**
 * The frame around every route: the top bar, a sidebar that is a permanent
 * column from 1024px up and a drawer below it (opened by the top bar's menu
 * button and closed by a link click, the backdrop or Escape), then the main
 * column with the demo banner above the routed view.
 */
export function AppShell(): ReactElement {
  const drawerRef = useRef<HTMLDivElement>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const mode = useServerMode();
  const match = useMatch("/projects/:projectId/*");
  const projectId = match?.params.projectId ?? null;

  useEffect(() => {
    if (!drawerOpen) {
      return undefined;
    }
    const previousFocus = document.activeElement as HTMLElement | null;
    const controls = () => Array.from(drawerRef.current?.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled])',
    ) ?? []);
    controls()[0]?.focus();
    function closeOnEscape(event: KeyboardEvent): void {
      if (event.key === "Tab") {
        const items = controls();
        const first = items[0];
        const last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
      if (event.key === "Escape") {
        setDrawerOpen(false);
      }
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => { window.removeEventListener("keydown", closeOnEscape); previousFocus?.focus(); };
  }, [drawerOpen]);

  function closeDrawer(): void {
    setDrawerOpen(false);
  }

  return (
    <div className="shell">
      <TopBar
        drawerOpen={drawerOpen}
        onToggleDrawer={() => setDrawerOpen((open) => !open)}
        drawerId={DRAWER_ID}
      />
      <div ref={drawerRef} id={DRAWER_ID} role={drawerOpen ? "dialog" : undefined} aria-modal={drawerOpen || undefined} aria-label={drawerOpen ? "Navigation" : undefined} className={drawerOpen ? "drawer drawer--open" : "drawer"}>
        <div className="drawer__backdrop" aria-hidden="true" onClick={closeDrawer} />
        <Sidebar projectId={projectId} onNavigate={closeDrawer} />
      </div>
      <main className="shell__main">
        <ModeBanner mode={mode} />
        <Outlet />
      </main>
    </div>
  );
}
