import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TRACKER_FIXTURE } from "../fixtures";
import { SPANNED_SCRIPT_FIXTURE } from "../fixtures/spans";
import { stubFetch } from "../testing/fetchStub";
import { renderWithProject } from "../testing/renderWithProject";
import { ScriptView } from "./ScriptView";

function renderScript(analysis = SPANNED_SCRIPT_FIXTURE) {
  stubFetch({ tracker: { status: 200, body: TRACKER_FIXTURE } });
  return renderWithProject(<ScriptView />, { analysis });
}

/** The paper and the rail both carry a finding's words, so a test that
 * means one of them has to say which. */
function paperOf(container: HTMLElement): HTMLElement {
  return container.querySelector<HTMLElement>(".script-paper") as HTMLElement;
}

function railOf(container: HTMLElement): HTMLElement {
  return container.querySelector<HTMLElement>(".suggestions") as HTMLElement;
}

describe("ScriptView", () => {
  it("offers Run analysis in a worded empty state when the project has no script", () => {
    stubFetch({ tracker: { status: 200, body: [] } });

    renderWithProject(<ScriptView />, { projectId: "demo x" });

    expect(screen.getByRole("heading", { name: "Script" })).toBeInTheDocument();
    expect(screen.getByText("No analysis has been run for this project.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Run analysis" })).toHaveAttribute(
      "href",
      "/projects/demo%20x/analyze",
    );
  });

  it("prints the script's lines once an analysis is on screen", () => {
    renderScript();

    expect(screen.getByText("INT. GARAGE - NIGHT")).toBeInTheDocument();
    expect(screen.queryByText(/No analysis has been run/)).toBeNull();
  });

  it("marks each finding the analysis sent offsets for", () => {
    renderScript();

    expect(screen.getByRole("button", { name: "Ferrari Testarossa" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hotel California" })).toBeInTheDocument();
  });

  it("lists the finding with no offsets in the rail and marks it nowhere", () => {
    const { container } = renderScript();

    expect(screen.getByText(/marked nowhere on the page/)).toBeInTheDocument();
    expect(screen.getByText(/Scene 3, page 8/)).toBeInTheDocument();
    expect(
      within(paperOf(container)).queryByRole("button", { name: /Lola's father/ }),
    ).toBeNull();
  });

  it("opens the finding's card in the rail when its highlight is clicked", () => {
    renderScript();

    fireEvent.click(screen.getByRole("button", { name: "Hotel California" }));

    expect(screen.getByText("Synchronization License")).toBeVisible();
    expect(screen.getByText("2 of 3")).toBeInTheDocument();
  });

  it("walks the findings in reading order with the stepper", () => {
    renderScript();

    fireEvent.click(screen.getByRole("button", { name: /Next issue/ }));
    expect(screen.getByText("1 of 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ferrari Testarossa" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    fireEvent.click(screen.getByRole("button", { name: /Next issue/ }));
    expect(screen.getByText("2 of 3")).toBeInTheDocument();
  });

  it("narrows the rail with a chip, leaving the paper and the counts alone", () => {
    const { container } = renderScript();

    fireEvent.click(screen.getByRole("button", { name: /^high risk/i }));

    expect(within(railOf(container)).queryByText("Ferrari Testarossa")).toBeNull();
    expect(within(paperOf(container)).getByText("Ferrari Testarossa")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^all/i })).toHaveTextContent("3");
  });

  it("counts the words of the script it is showing", () => {
    renderScript();

    expect(screen.getByText("56 words")).toBeInTheDocument();
  });

  it("draws the formatting controls disabled, with the reason", () => {
    renderScript();

    expect(screen.getByRole("button", { name: "Bold" })).toBeDisabled();
    expect(screen.getByText(/has no endpoint that writes one/)).toBeInTheDocument();
  });

  it("zooms the paper", () => {
    renderScript();

    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));

    expect(screen.getByText("125%")).toBeInTheDocument();
  });

  it("shows the tracker's verdict beside a finding once the tracker answers", async () => {
    renderScript();

    await waitFor(() => {
      expect(screen.getByText(/Scene 1, page 3 · Blocked/)).toBeInTheDocument();
    });
  });

  it("shows the server's sentence when the script could not be read", () => {
    stubFetch({
      tracker: { status: 200, body: [] },
      scripts: { status: 503, body: { detail: "the script store is unreachable" } },
    });

    renderWithProject(<ScriptView />);

    expect(screen.getByRole("heading", { name: "Script" })).toBeInTheDocument();
  });
});
