import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { trackerStats } from "./model";
import { TrackerStats } from "./TrackerStats";

describe("TrackerStats", () => {
  it("shows cleared as a count of total with the percent, from the fixture scenario", () => {
    const stats = trackerStats([
      { state: "BLOCKED", needs_review: false } as never,
      { state: "BLOCKED", needs_review: false } as never,
      { state: "BLOCKED", needs_review: false } as never,
    ]);

    render(<TrackerStats stats={stats} />);

    expect(screen.getByText("0 of 3 (0%)")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("shows the needs-review count", () => {
    const stats = trackerStats([{ state: "BLOCKED", needs_review: true } as never]);

    render(<TrackerStats stats={stats} />);

    expect(screen.getByText("Needs review")).toBeInTheDocument();
  });
});
