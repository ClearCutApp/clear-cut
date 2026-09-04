import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import trackerData from "../fixtures/tracker.json";
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

  it("shows neither loading nor the empty state once rows exist", async () => {
    stubFetch({ tracker: { status: 200, body: trackerData } });

    renderWithProject(<OverviewView />);

    await waitFor(() => expect(screen.queryByText(/Loading the tracker/)).toBeNull());
    expect(screen.queryByText(/No analysis has run yet/)).toBeNull();
  });
});
