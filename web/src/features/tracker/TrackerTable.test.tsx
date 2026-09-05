import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Category } from "../../api/client";
import { TRACKER_FIXTURE } from "../../fixtures";
import { groupByState } from "./model";
import { TrackerTable } from "./TrackerTable";

const items = TRACKER_FIXTURE;

const noCategory = () => null;

function renderTable({
  groups = groupByState(items),
  selectedItemId = null as string | null,
  onSelect = vi.fn(),
  categoryFor = noCategory as (itemId: string) => Category | null,
} = {}) {
  render(
    <TrackerTable
      groups={groups}
      selectedItemId={selectedItemId}
      onSelect={onSelect}
      categoryFor={categoryFor}
    />,
  );
  return onSelect;
}

describe("TrackerTable", () => {
  it("renders the three fixture rows under one BLOCKED heading", () => {
    renderTable();

    expect(screen.getByRole("heading", { name: "BLOCKED" })).toBeInTheDocument();
    expect(screen.getAllByText(/^Open EVT-/).length).toBe(3);
  });

  it("names its columns, Type among them", () => {
    renderTable();

    for (const column of ["State", "Finding", "Required document", "Type", "Contact", "Scenes"]) {
      expect(screen.getByText(column)).toBeInTheDocument();
    }
  });

  it("asks for each row's category by item id", () => {
    const categoryFor = vi.fn((itemId: string) =>
      itemId === "EVT-001" ? ("INDUSTRIAL_PROPERTY" as Category) : null,
    );

    renderTable({ categoryFor });

    expect(screen.getByText("Industrial property")).toBeInTheDocument();
    expect(screen.getAllByText("unknown")).toHaveLength(2);
  });

  it("shows the worded empty state when no groups match the current filter", () => {
    renderTable({ groups: [] });

    expect(screen.getByText("No items match the current filter.")).toBeInTheDocument();
  });

  it("passes the selected item id through so its row shows aria-current", () => {
    renderTable({ selectedItemId: items[0].item_id });

    expect(screen.getByRole("button", { name: "Open EVT-001" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(screen.getByRole("button", { name: "Open EVT-002" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("calls onSelect with the clicked row's item id", () => {
    const onSelect = renderTable();

    fireEvent.click(screen.getByRole("button", { name: "Open EVT-002" }));

    expect(onSelect).toHaveBeenCalledWith("EVT-002");
  });
});
