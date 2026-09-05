import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { TrackerItem } from "../../api/client";
import trackerFixture from "../../fixtures/tracker.json";
import { groupByState } from "./model";
import { TrackerTable } from "./TrackerTable";

const items = trackerFixture as TrackerItem[];

describe("TrackerTable", () => {
  it("renders the three fixture rows under one BLOCKED heading", () => {
    render(
      <TrackerTable groups={groupByState(items)} selectedItemId={null} onSelect={vi.fn()} />,
    );

    expect(screen.getByRole("heading", { name: "BLOCKED" })).toBeInTheDocument();
    expect(screen.getAllByText(/^Open EVT-/).length).toBe(3);
  });

  it("shows the worded empty state when no groups match the current filter", () => {
    render(<TrackerTable groups={[]} selectedItemId={null} onSelect={vi.fn()} />);

    expect(screen.getByText("No items match the current filter.")).toBeInTheDocument();
  });

  it("passes the selected item id through so its row shows aria-current", () => {
    render(
      <TrackerTable
        groups={groupByState(items)}
        selectedItemId={items[0].item_id}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Open EVT-001" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(screen.getByRole("button", { name: "Open EVT-002" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("calls onSelect with the clicked row's item id", () => {
    const onSelect = vi.fn();
    render(
      <TrackerTable groups={groupByState(items)} selectedItemId={null} onSelect={onSelect} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open EVT-002" }));

    expect(onSelect).toHaveBeenCalledWith("EVT-002");
  });
});
