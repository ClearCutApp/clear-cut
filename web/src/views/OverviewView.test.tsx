import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ItemDetailPanelHost } from "../features/item/ItemDetailPanelHost";
import { SCRIPT_FIXTURE, TRACKER_FIXTURE } from "../fixtures";
import { stubFetch, type StubRoute } from "../testing/fetchStub";
import { renderWithProject } from "../testing/renderWithProject";
import { OverviewView } from "./OverviewView";

function ok(body: unknown) {
  return { status: 200, body };
}

/** The tracker is what these tests are about; the project and script reads
 * are stubbed to nothing so their absence never speaks over it. */
function stub(routes: Record<string, StubRoute>) {
  return stubFetch({ scripts: ok([]), ...routes });
}

describe("OverviewView", () => {
  it("says it is loading until the tracker answers", () => {
    stub({ tracker: ok([]) });

    renderWithProject(<OverviewView />);

    expect(screen.getByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByText(/Loading the tracker/)).toBeInTheDocument();
  });

  it("shows the server's sentence when the tracker request fails", async () => {
    stub({ tracker: { status: 500, body: "internal error" } });

    renderWithProject(<OverviewView />);

    expect(await screen.findByRole("alert")).toHaveTextContent("internal error");
    expect(screen.queryByText(/Loading the tracker/)).toBeNull();
  });

  it("offers Run analysis in a worded empty state when no analysis ever ran", async () => {
    stub({ tracker: ok([]) });

    renderWithProject(<OverviewView />, { projectId: "demo x" });

    expect(
      await screen.findByText("No analysis has run yet for this project."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Run analysis" })).toHaveAttribute(
      "href",
      "/projects/demo%20x/analyze",
    );
  });

  it("renders the three fixture rows under one BLOCKED group once the tracker answers", async () => {
    stub({ tracker: ok(TRACKER_FIXTURE) });

    renderWithProject(<OverviewView />);

    expect(await screen.findByRole("heading", { name: "BLOCKED" })).toBeInTheDocument();
    expect(screen.getAllByText(/^Open EVT-/)).toHaveLength(3);
    expect(screen.queryByText(/Loading the tracker/)).toBeNull();
    expect(screen.queryByText(/No analysis has run yet/)).toBeNull();
  });

  it("draws the cleared ring over the whole tracker", async () => {
    stub({ tracker: ok(TRACKER_FIXTURE) });

    const { container } = renderWithProject(<OverviewView />);
    await screen.findByRole("heading", { name: "BLOCKED" });

    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByText("0 of 3 items")).toBeInTheDocument();
    expect(container.querySelector(".tracker-donut")).toBeInTheDocument();
  });

  it("fills the Type column from the loaded script's findings", async () => {
    stub({ tracker: ok(TRACKER_FIXTURE) });

    renderWithProject(<OverviewView />, { analysis: SCRIPT_FIXTURE });

    await screen.findByRole("heading", { name: "BLOCKED" });
    expect(screen.getByText("Industrial property")).toBeInTheDocument();
    expect(screen.getByText("Continuity")).toBeInTheDocument();
    expect(screen.queryByText("unknown")).toBeNull();
  });

  it("says the type is unknown for every row when no script is loaded", async () => {
    stub({ tracker: ok(TRACKER_FIXTURE) });

    renderWithProject(<OverviewView />);

    await screen.findByRole("heading", { name: "BLOCKED" });
    expect(screen.getAllByText("unknown")).toHaveLength(3);
  });

  it("narrows the table to the pill's state when a filter pill is clicked", async () => {
    stub({ tracker: ok(TRACKER_FIXTURE) });

    renderWithProject(<OverviewView />);
    await screen.findByRole("heading", { name: "BLOCKED" });

    fireEvent.click(screen.getByRole("button", { name: /needs review/i }));

    await waitFor(() =>
      expect(screen.getByText("No items match the current filter.")).toBeInTheDocument(),
    );
  });

  it("narrows the table to rows matching a search term", async () => {
    stub({ tracker: ok(TRACKER_FIXTURE) });

    renderWithProject(<OverviewView />);
    await screen.findByRole("heading", { name: "BLOCKED" });

    fireEvent.change(screen.getByLabelText(/search/i), {
      target: { value: "warnerchappell" },
    });

    await waitFor(() => expect(screen.getAllByText(/^Open EVT-/)).toHaveLength(1));
    expect(screen.getByRole("button", { name: "Open EVT-002" })).toBeInTheDocument();
  });

  it("opens the item detail panel when a row's Open button is clicked, and marks the row", async () => {
    stub({ tracker: ok(TRACKER_FIXTURE) });

    const { container } = renderWithProject(
      <>
        <OverviewView />
        <ItemDetailPanelHost />
      </>,
    );
    await screen.findByRole("heading", { name: "BLOCKED" });

    fireEvent.click(screen.getByRole("button", { name: "Open EVT-001" }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(container.querySelectorAll(".tracker-row--selected")).toHaveLength(1);
  });
});
