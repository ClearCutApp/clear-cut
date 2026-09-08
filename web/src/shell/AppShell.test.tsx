import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";

import { ServerModeProvider } from "../state/ServerModeContext";
import { stubFetch } from "../testing/fetchStub";
import { AppShell } from "./AppShell";

function renderShell(path = "/", mode = "live") {
  stubFetch({ health: { status: 200, body: { mode } } });
  render(
    <MemoryRouter initialEntries={[path]}>
      <ServerModeProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<p>home view</p>} />
            <Route path="projects" element={<p>projects view</p>} />
            <Route path="projects/:projectId/*" element={<p>project view</p>} />
          </Route>
        </Routes>
      </ServerModeProvider>
    </MemoryRouter>,
  );
}

function menuButton() {
  return screen.getByRole("button", { name: "Menu" });
}

describe("AppShell", () => {
  it("frames the routed view with the brand and the Projects link", () => {
    renderShell();

    expect(screen.getAllByText("ClearCut").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Projects" })).toBeInTheDocument();
    expect(screen.getByText("home view")).toBeInTheDocument();
  });

  it("toggles the drawer through the menu button's aria-expanded", () => {
    renderShell();

    expect(menuButton()).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(menuButton());
    expect(menuButton()).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(menuButton());
    expect(menuButton()).toHaveAttribute("aria-expanded", "false");
  });

  it("closes the drawer on Escape and on a navigation link", () => {
    renderShell();

    fireEvent.click(menuButton());
    fireEvent.keyDown(window, { key: "Escape" });
    expect(menuButton()).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(menuButton());
    fireEvent.click(screen.getByRole("link", { name: "Projects" }));
    expect(menuButton()).toHaveAttribute("aria-expanded", "false");
  });

  it("shows the project tabs only while a project route is open", () => {
    renderShell("/projects/demo%20x/ask");

    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("href", "/projects/demo%20x");
    expect(screen.getByText("project view")).toBeInTheDocument();
  });

  it("shows the demo banner when the health endpoint answers mock", async () => {
    renderShell("/", "mock");

    expect(await screen.findByTestId("mode-banner")).toBeInTheDocument();
  });

  it("shows no banner when the health endpoint answers live", async () => {
    const { calls } = stubFetch({ health: { status: 200, body: { mode: "live" } } });
    render(
      <MemoryRouter>
        <ServerModeProvider>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<p>home view</p>} />
            <Route path="projects" element={<p>projects view</p>} />
            </Route>
          </Routes>
        </ServerModeProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(calls.filter((call) => call.kind === "health")).toHaveLength(1));
    expect(screen.queryByTestId("mode-banner")).toBeNull();
  });

  it("keeps unavailable destinations out of the working navigation", () => {
    renderShell();

    expect(screen.queryByText("Notifications")).toBeNull();
    expect(screen.queryByText("Settings")).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.queryByRole("searchbox")).toBeNull();
    expect(screen.queryByRole("button", { name: /settings|notifications/i })).toBeNull();
  });
});
