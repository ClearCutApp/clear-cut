import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { TrackerItem } from "../../api/client";
import { trackerStats } from "./model";
import { TrackerStats } from "./TrackerStats";

function item(overrides: Partial<TrackerItem>): TrackerItem {
  return { state: "BLOCKED", needs_review: false, ...overrides } as TrackerItem;
}

describe("TrackerStats", () => {
  it("prints the cleared percent inside the ring, never only as a sweep", () => {
    const stats = trackerStats([
      item({ state: "CLEARED" }),
      item({ state: "CLEARED" }),
      item({ state: "BLOCKED" }),
      item({ state: "IN_PROGRESS" }),
    ]);

    const { container } = render(<TrackerStats stats={stats} />);

    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(container.querySelector(".tracker-donut")).toHaveStyle({
      "--cleared-percent": "50",
    });
  });

  it("says how many of how many are cleared, in words", () => {
    const stats = trackerStats([item({ state: "CLEARED" }), item({ state: "BLOCKED" })]);

    render(<TrackerStats stats={stats} />);

    expect(screen.getByText("Cleared")).toBeInTheDocument();
    expect(screen.getByText("1 of 2 items")).toBeInTheDocument();
  });

  it("shows the three counts a reader scans after the ring", () => {
    const stats = trackerStats([
      item({ state: "BLOCKED" }),
      item({ state: "IN_PROGRESS" }),
      item({ state: "CLEARED", needs_review: true }),
    ]);

    render(<TrackerStats stats={stats} />);

    for (const label of ["Blocked", "In progress", "Needs review"]) {
      expect(screen.getByText(label).previousSibling).toHaveTextContent("1");
    }
  });

  it("draws an empty ring at zero rather than hiding it", () => {
    const stats = trackerStats([item({ state: "BLOCKED" })]);

    render(<TrackerStats stats={stats} />);

    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByText("0 of 1 items")).toBeInTheDocument();
  });
});
