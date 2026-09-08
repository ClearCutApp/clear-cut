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
    expect(screen.getByRole("link", { name: "Projects" })).toHaveAttribute("href", "/projects");
    expect(screen.queryByRole("link", { name: "Overview" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Script" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Ask" })).toBeNull();
    expect(screen.getByText(/open once a project is open/)).toBeInTheDocument();
  });

  it("adds Dashboard, Script and Ask with the project id encoded", () => {
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

  it("shows only destinations the current workspace serves", () => {
    renderSidebar("p");
    expect(screen.queryByText("Settings")).toBeNull();
    expect(screen.queryByText(/no resource in the API/)).toBeNull();
    expect(screen.getAllByRole("link")).toHaveLength(12);
    expect(screen.getByRole("link", { name: "Notifications" })).toHaveAttribute("href", "/projects/p/notifications");
    expect(screen.getByRole("link", { name: "Reports" })).toHaveAttribute("href", "/projects/p/reports");
    expect(screen.getByRole("link", { name: "Write" })).toHaveAttribute("href", "/projects/p/editor");
  });

  it("invents no company, no user and no search box", () => {
    renderSidebar("p");

    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.queryByRole("searchbox")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByRole("img")).toBeNull();
  });
});
