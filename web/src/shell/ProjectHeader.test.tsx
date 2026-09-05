import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SCRIPT_FIXTURE } from "../fixtures";
import { rememberProject } from "../state/recentProjects";
import { stubFetch } from "../testing/fetchStub";
import { renderWithProject } from "../testing/renderWithProject";
import { ProjectHeader } from "./ProjectHeader";

const PROJECT = {
  project_id: "proj_1",
  title: "El Ultimo Verano",
  jurisdiction_code: "GB",
  created_at: "2026-09-01T10:00:00Z",
};

function ok(body: unknown) {
  return { status: 200, body };
}

describe("ProjectHeader", () => {
  it("falls back to the project id when the project resource has not answered", () => {
    stubFetch({ tracker: ok([]), scripts: ok([]) });
    rememberProject("proj_1", "GB");

    renderWithProject(<ProjectHeader />, { projectId: "proj_1" });

    expect(screen.getByRole("heading", { name: "proj_1" })).toBeInTheDocument();
    expect(screen.getByText("United Kingdom")).toBeInTheDocument();
  });

  it("shows the project's title with its id still on screen", async () => {
    stubFetch({ tracker: ok([]), scripts: ok([]), project: ok(PROJECT) });

    renderWithProject(<ProjectHeader />, { projectId: "proj_1" });

    expect(
      await screen.findByRole("heading", { name: "El Ultimo Verano" }),
    ).toBeInTheDocument();
    expect(screen.getByText("proj_1")).toBeInTheDocument();
    expect(screen.getByText("United Kingdom")).toBeInTheDocument();
  });

  it("says so when the project resource refuses, and keeps the id as the title", async () => {
    stubFetch({
      tracker: ok([]),
      scripts: ok([]),
      project: { status: 404, body: "no such project" },
    });

    renderWithProject(<ProjectHeader />, { projectId: "proj_1" });

    expect(await screen.findByRole("alert")).toHaveTextContent("no such project");
    expect(screen.getByRole("heading", { name: "proj_1" })).toBeInTheDocument();
  });

  it("offers Run analysis and no version before an analysis runs", () => {
    stubFetch({ tracker: ok([]), scripts: ok([]) });

    renderWithProject(<ProjectHeader />, { projectId: "demo x" });

    expect(screen.getByRole("link", { name: "Run analysis" })).toHaveAttribute(
      "href",
      "/projects/demo%20x/analyze",
    );
    expect(screen.queryByText(/Script v/)).toBeNull();
  });

  it("shows Script v1 and offers a new version once a script is loaded", () => {
    stubFetch({ tracker: ok([]), scripts: ok([]) });

    renderWithProject(<ProjectHeader />, { analysis: SCRIPT_FIXTURE });

    expect(screen.getByText("Script v1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Upload new version" })).toBeInTheDocument();
  });
});
