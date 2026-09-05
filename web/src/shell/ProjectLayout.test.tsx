import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";

import { TRACKER_FIXTURE } from "../fixtures";
import { useProject } from "../state/ProjectContext";
import { stubFetch } from "../testing/fetchStub";
import { ProjectLayout } from "./ProjectLayout";

function SelectProbe() {
  const { projectId, selectItem } = useProject();
  return (
    <button type="button" onClick={() => selectItem("EVT-001")}>
      select in {projectId}
    </button>
  );
}

function renderLayout(path: string) {
  stubFetch({ tracker: { status: 200, body: TRACKER_FIXTURE } });
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="projects/:projectId" element={<ProjectLayout />}>
          <Route index element={<SelectProbe />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProjectLayout", () => {
  it("provides the decoded project id from the route to its children", () => {
    renderLayout("/projects/demo%20x");

    expect(screen.getByRole("heading", { name: "demo x" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "select in demo x" })).toBeInTheDocument();
  });

  it("opens the panel column when an item is selected and closes it again", () => {
    const { container } = renderLayout("/projects/p");
    const frame = container.querySelector(".project-layout");

    expect(frame).not.toHaveClass("project-layout--panel-open");
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "select in p" }));

    expect(frame).toHaveClass("project-layout--panel-open");
    expect(screen.getByRole("dialog")).toHaveTextContent("EVT-001");

    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(frame).not.toHaveClass("project-layout--panel-open");
  });
});
