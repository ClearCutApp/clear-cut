import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { rememberProject } from "../state/recentProjects";
import { ProjectsView } from "./ProjectsView";

function renderView() {
  render(
    <MemoryRouter>
      <ProjectsView />
    </MemoryRouter>,
  );
}

describe("ProjectsView", () => {
  it("says plainly when this browser has opened no project", () => {
    renderView();

    expect(screen.getByRole("heading", { name: "Projects" })).toBeInTheDocument();
    expect(screen.getByText("No projects opened in this browser yet.")).toBeInTheDocument();
  });

  it("drops the empty sentence once a project was opened", () => {
    rememberProject("proj_1", "US");

    renderView();

    expect(screen.queryByText(/No projects opened/)).toBeNull();
  });
});
