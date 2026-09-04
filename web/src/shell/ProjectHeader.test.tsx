import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AnalyzeResponse } from "../api/client";
import analyzeData from "../fixtures/analyze.json";
import { rememberProject } from "../state/recentProjects";
import { renderWithProject } from "../testing/renderWithProject";
import { ProjectHeader } from "./ProjectHeader";

const analyzeFixture = analyzeData as AnalyzeResponse;

describe("ProjectHeader", () => {
  it("shows the project id and the jurisdiction's name", () => {
    rememberProject("proj_1", "GB");

    renderWithProject(<ProjectHeader />, { projectId: "proj_1" });

    expect(screen.getByRole("heading", { name: "proj_1" })).toBeInTheDocument();
    expect(screen.getByText("United Kingdom")).toBeInTheDocument();
  });

  it("offers Run analysis and no version before an analysis runs in session", () => {
    renderWithProject(<ProjectHeader />, { projectId: "demo x" });

    expect(screen.getByRole("link", { name: "Run analysis" })).toHaveAttribute(
      "href",
      "/projects/demo%20x/analyze",
    );
    expect(screen.queryByText(/Script v/)).toBeNull();
  });

  it("shows Script v1 and offers a new version once an analysis is in session", () => {
    renderWithProject(<ProjectHeader />, { analysis: analyzeFixture });

    expect(screen.getByText("Script v1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Upload new version" })).toBeInTheDocument();
  });
});
