import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Category, TrackerItem } from "../../api/client";
import { TRACKER_FIXTURE } from "../../fixtures";
import { TrackerRow } from "./TrackerRow";

const ferrariItem = TRACKER_FIXTURE[0];
const continuityItem = TRACKER_FIXTURE[2];

interface RowOptions {
  category?: Category | null;
  selected?: boolean;
  onSelect?: (itemId: string) => void;
}

function renderRow(
  item: TrackerItem,
  { category = null, selected = false, onSelect = vi.fn() }: RowOptions = {},
) {
  const result = render(
    <TrackerRow
      item={item}
      category={category}
      selected={selected}
      onSelect={onSelect}
    />,
  );
  return { ...result, onSelect };
}

describe("TrackerRow", () => {
  it("renders the state badge, finding id, document, contact and scene label", () => {
    renderRow(ferrariItem);

    expect(screen.getByTestId("state-badge")).toHaveTextContent("BLOCKED");
    expect(screen.getByText("EVT-001")).toBeInTheDocument();
    expect(screen.getByText("Trademark Clearance Form")).toBeInTheDocument();
    expect(screen.getByText(/legal@ferrari\.example/)).toBeInTheDocument();
    expect(screen.getByText("Scene 1")).toBeInTheDocument();
  });

  it("names the finding's category in words in the Type column", () => {
    renderRow(ferrariItem, { category: "INDUSTRIAL_PROPERTY" });

    expect(screen.getByText("Industrial property")).toBeInTheDocument();
  });

  it("says the type is unknown when no script is loaded to join it to", () => {
    renderRow(ferrariItem);

    expect(screen.getByText("unknown")).toBeInTheDocument();
  });

  it("shows 'no contact on file' when contact is an empty string", () => {
    renderRow(continuityItem);

    expect(screen.getByText(/no contact on file/i)).toBeInTheDocument();
  });

  it("renders no NeedsReviewBadge when needs_review is false", () => {
    renderRow(ferrariItem);

    expect(screen.queryByText("NEEDS_REVIEW")).toBeNull();
  });

  it("renders the NeedsReviewBadge when needs_review is true", () => {
    renderRow({ ...ferrariItem, needs_review: true });

    expect(screen.getByText("NEEDS_REVIEW")).toBeInTheDocument();
  });

  it("opens the item on a button covering the row, and carries no other action button", () => {
    const { onSelect } = renderRow(ferrariItem);

    fireEvent.click(screen.getByRole("button", { name: "Open EVT-001" }));

    expect(onSelect).toHaveBeenCalledWith("EVT-001");
    expect(screen.queryByRole("button", { name: /draft email/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /notify/i })).toBeNull();
  });

  it("marks the row aria-current and carries the selected class when selected", () => {
    const { container } = renderRow(ferrariItem, { selected: true });

    expect(screen.getByRole("button", { name: "Open EVT-001" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(container.firstChild).toHaveClass("tracker-row--selected");
  });

  it("leaves aria-current and the selected class off an unselected row", () => {
    const { container } = renderRow(ferrariItem);

    expect(screen.getByRole("button", { name: "Open EVT-001" })).not.toHaveAttribute(
      "aria-current",
    );
    expect(container.firstChild).not.toHaveClass("tracker-row--selected");
  });
});
