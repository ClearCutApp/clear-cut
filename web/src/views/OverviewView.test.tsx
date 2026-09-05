import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import trackerData from "../fixtures/tracker.json";
import { ItemDetailPanelHost } from "../features/item/ItemDetailPanelHost";
import { stubFetch } from "../testing/fetchStub";
import { renderWithProject } from "../testing/renderWithProject";
import { OverviewView } from "./OverviewView";

describe("OverviewView", () => {
  it("says it is loading until the tracker answers", () => {
    stubFetch({ tracker: { status: 200, body: [] } });

    renderWithProject(<OverviewView />);

    expect(screen.getByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByText(/Loading the tracker/)).toBeInTheDocument();
  });

  it("shows the server's sentence when the tracker request fails", async () => {
    stubFetch({ tracker: { status: 500, body: "internal error" } });

    renderWithProject(<OverviewView />);

    expect(await screen.findByRole("alert")).toHaveTextContent("internal error");
    expect(screen.queryByText(/Loading the tracker/)).toBeNull();
  });

  it("offers Run analysis in a worded empty state when no analysis ever ran", async () => {
    stubFetch({ tracker: { status: 200, body: [] } });

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
    stubFetch({ tracker: { status: 200, body: trackerData } });

    renderWithProject(<OverviewView />);

    expect(await screen.findByRole("heading", { name: "BLOCKED" })).toBeInTheDocument();
    expect(screen.getAllByText(/^Open EVT-/)).toHaveLength(3);
    expect(screen.queryByText(/Loading the tracker/)).toBeNull();
    expect(screen.queryByText(/No analysis has run yet/)).toBeNull();
  });

  it("narrows the table to the pill's state when a filter pill is clicked", async () => {
    stubFetch({ tracker: { status: 200, body: trackerData } });

    renderWithProject(<OverviewView />);
    await screen.findByRole("heading", { name: "BLOCKED" });

    fireEvent.click(screen.getByRole("button", { name: /needs review/i }));

    await waitFor(() =>
      expect(screen.getByText("No items match the current filter.")).toBeInTheDocument(),
    );
  });

  it("narrows the table to rows matching a search term", async () => {
    stubFetch({ tracker: { status: 200, body: trackerData } });

    renderWithProject(<OverviewView />);
    await screen.findByRole("heading", { name: "BLOCKED" });

    fireEvent.change(screen.getByLabelText(/search/i), {
      target: { value: "warnerchappell" },
    });

    await waitFor(() => expect(screen.getAllByText(/^Open EVT-/)).toHaveLength(1));
    expect(screen.getByRole("button", { name: "Open EVT-002" })).toBeInTheDocument();
  });

  it("opens the item detail panel when a row's Open button is clicked", async () => {
    stubFetch({ tracker: { status: 200, body: trackerData } });

    renderWithProject(
      <>
        <OverviewView />
        <ItemDetailPanelHost />
      </>,
    );
    await screen.findByRole("heading", { name: "BLOCKED" });

    fireEvent.click(screen.getByRole("button", { name: "Open EVT-001" }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });
});
