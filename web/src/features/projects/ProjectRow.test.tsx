import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { Project } from "../../api/client";
import { ProjectRow } from "./ProjectRow";

const PROJECT: Project = {
  project_id: "prj 4f2a",
  title: "El Ultimo Verano",
  jurisdiction_code: "AR",
  created_at: "2026-09-01T10:00:00Z",
};

function renderRow(project: Project = PROJECT) {
  return render(
    <MemoryRouter>
      <ProjectRow project={project} />
    </MemoryRouter>,
  );
}

describe("ProjectRow", () => {
  it("shows the title, the id and the jurisdiction in words", () => {
    renderRow();

    expect(screen.getByRole("heading", { name: "El Ultimo Verano" })).toBeInTheDocument();
    expect(screen.getByText("prj 4f2a")).toBeInTheDocument();
    expect(screen.getByText("Argentina")).toBeInTheDocument();
  });

  it("opens the project at its encoded path", () => {
    renderRow();

    expect(
      screen.getByRole("link", { name: "Open El Ultimo Verano" }),
    ).toHaveAttribute("href", "/projects/prj%204f2a");
  });

  it("carries the creation stamp as a machine-readable time", () => {
    const { container } = renderRow();

    expect(container.querySelector("time")).toHaveAttribute(
      "dateTime",
      "2026-09-01T10:00:00Z",
    );
  });

  it("shows an unreadable stamp verbatim rather than as Invalid Date", () => {
    renderRow({ ...PROJECT, created_at: "whenever" });

    expect(screen.getByText("whenever")).toBeInTheDocument();
  });

  it("draws no poster, no team and no progress the API never sent", () => {
    const { container } = renderRow();

    expect(container.querySelector("img")).toBeNull();
    expect(screen.queryByText(/team member|updated|% cleared/i)).toBeNull();
    expect(container.querySelector("progress")).toBeNull();
  });
});
