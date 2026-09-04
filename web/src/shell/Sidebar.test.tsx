import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { API_DOCS_PATH } from "../api/client";
import { Sidebar } from "./Sidebar";

function renderSidebar(projectId: string | null, path = "/", onNavigate = vi.fn()) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Sidebar projectId={projectId} onNavigate={onNavigate} />
    </MemoryRouter>,
  );
  return onNavigate;
}

describe("Sidebar", () => {
  it("shows the brand and Projects, and no project tabs, outside a project", () => {
    renderSidebar(null);

    expect(screen.getByText("ClearCut")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Projects" })).toHaveAttribute("href", "/");
    expect(screen.queryByRole("link", { name: "Overview" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Script" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Ask" })).toBeNull();
  });

  it("adds Overview, Script and Ask with the project id encoded", () => {
    renderSidebar("demo x", "/projects/demo%20x");

    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("href", "/projects/demo%20x");
    expect(screen.getByRole("link", { name: "Script" })).toHaveAttribute("href", "/projects/demo%20x/script");
    expect(screen.getByRole("link", { name: "Ask" })).toHaveAttribute("href", "/projects/demo%20x/ask");
  });

  it("marks only the current route's tab as current", () => {
    renderSidebar("p", "/projects/p/script");

    expect(screen.getByRole("link", { name: "Script" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: "Projects" })).not.toHaveAttribute("aria-current");
  });

  it("links to the API docs at the client's constant", () => {
    renderSidebar(null);

    expect(screen.getByRole("link", { name: "API docs" })).toHaveAttribute("href", API_DOCS_PATH);
  });

  it("reports every navigation so a drawer can close", () => {
    const onNavigate = renderSidebar("p");

    fireEvent.click(screen.getByRole("link", { name: "Ask" }));

    expect(onNavigate).toHaveBeenCalledTimes(1);
  });

  it("draws nothing the server cannot back: no selector, settings, notifications or search", () => {
    renderSidebar("p");

    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.queryByRole("searchbox")).toBeNull();
    expect(screen.queryByText(/settings|notifications|team|reports|log out/i)).toBeNull();
    expect(screen.getAllByRole("link")).toHaveLength(5);
  });
});
