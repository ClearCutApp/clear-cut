import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SCRIPT_FIXTURE } from "../fixtures";
import { stubFetch } from "../testing/fetchStub";
import { renderWithProject } from "../testing/renderWithProject";
import { ScriptView } from "./ScriptView";


describe("ScriptView", () => {
  it("offers Run analysis in a worded empty state when no analysis is in session", () => {
    stubFetch({ tracker: { status: 200, body: [] } });

    renderWithProject(<ScriptView />, { projectId: "demo x" });

    expect(screen.getByRole("heading", { name: "Script" })).toBeInTheDocument();
    expect(screen.getByText("No analysis is loaded in this session.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Run analysis" })).toHaveAttribute(
      "href",
      "/projects/demo%20x/analyze",
    );
  });

  it("drops the empty state once an analysis is in session", () => {
    stubFetch({ tracker: { status: 200, body: [] } });

    renderWithProject(<ScriptView />, { analysis: SCRIPT_FIXTURE });

    expect(screen.queryByText(/No analysis is loaded/)).toBeNull();
  });
});
