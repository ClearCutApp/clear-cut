import { fireEvent, screen, waitFor } from "@testing-library/react";
import { Link } from "react-router";
import { describe, expect, it } from "vitest";

import { SCRIPT_FIXTURE } from "../fixtures";
import { useProject } from "../state/ProjectContext";
import { stubFetch } from "./fetchStub";
import { renderWithProject } from "./renderWithProject";


function Probe() {
  const { projectId, analysis, selectedItemId, tracker } = useProject();
  return (
    <>
      <p>project {projectId}</p>
      <p>version {analysis?.version ?? "none"}</p>
      <p>selected {selectedItemId ?? "none"}</p>
      <p>rows {tracker?.length ?? "loading"}</p>
      <Link to="/projects/x/script">go</Link>
    </>
  );
}

describe("renderWithProject", () => {
  it("mounts the ui under a provider for the given project", async () => {
    stubFetch({ tracker: { status: 200, body: [] } });

    renderWithProject(<Probe />, { projectId: "demo x" });

    expect(screen.getByText("project demo x")).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/projects/demo%20x");
    await waitFor(() => expect(screen.getByText("rows 0")).toBeInTheDocument());
  });

  it("preloads an analysis and a selection when asked", async () => {
    stubFetch({ tracker: { status: 200, body: [] } });

    renderWithProject(<Probe />, { analysis: SCRIPT_FIXTURE, selectedItemId: "EVT-001" });

    expect(screen.getByText("version 1")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("selected EVT-001")).toBeInTheDocument());
  });

  it("reports a navigation through the location probe", () => {
    stubFetch({ tracker: { status: 200, body: [] } });

    renderWithProject(<Probe />);
    fireEvent.click(screen.getByRole("link", { name: "go" }));

    expect(screen.getByTestId("location")).toHaveTextContent("/projects/x/script");
  });
});
