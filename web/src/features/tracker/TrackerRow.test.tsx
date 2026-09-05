import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { TrackerItem } from "../../api/client";
import { TRACKER_FIXTURE } from "../../fixtures";
import { TrackerRow } from "./TrackerRow";

const ferrariItem = TRACKER_FIXTURE[0] as TrackerItem;
const continuityItem = TRACKER_FIXTURE[2] as TrackerItem;

describe("TrackerRow", () => {
  it("renders the state badge, finding id, document, contact and scene label", () => {
    render(<TrackerRow item={ferrariItem} selected={false} onSelect={vi.fn()} />);

    expect(screen.getByTestId("state-badge")).toHaveTextContent("BLOCKED");
    expect(screen.getByText("EVT-001")).toBeInTheDocument();
    expect(screen.getByText("Trademark Clearance Form")).toBeInTheDocument();
    expect(screen.getByText(/legal@ferrari\.example/)).toBeInTheDocument();
    expect(screen.getByText("Scene 1")).toBeInTheDocument();
  });

  it("shows 'no contact on file' when contact is an empty string", () => {
    render(<TrackerRow item={continuityItem} selected={false} onSelect={vi.fn()} />);

    expect(screen.getByText(/no contact on file/i)).toBeInTheDocument();
  });

  it("renders no NeedsReviewBadge when needs_review is false", () => {
    render(<TrackerRow item={ferrariItem} selected={false} onSelect={vi.fn()} />);

    expect(screen.queryByText("NEEDS_REVIEW")).toBeNull();
  });

  it("renders the NeedsReviewBadge when needs_review is true", () => {
    const flagged: TrackerItem = { ...ferrariItem, needs_review: true };
    render(<TrackerRow item={flagged} selected={false} onSelect={vi.fn()} />);

    expect(screen.getByText("NEEDS_REVIEW")).toBeInTheDocument();
  });

  it("opens the item on a button covering the row, and carries no other action button", () => {
    const onSelect = vi.fn();
    render(<TrackerRow item={ferrariItem} selected={false} onSelect={onSelect} />);

    fireEvent.click(screen.getByRole("button", { name: "Open EVT-001" }));

    expect(onSelect).toHaveBeenCalledWith("EVT-001");
    expect(screen.queryByRole("button", { name: /draft email/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /notify/i })).toBeNull();
  });

  it("marks the row aria-current when selected", () => {
    render(<TrackerRow item={ferrariItem} selected onSelect={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Open EVT-001" })).toHaveAttribute(
      "aria-current",
      "true",
    );
  });

  it("leaves aria-current absent when not selected", () => {
    render(<TrackerRow item={ferrariItem} selected={false} onSelect={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Open EVT-001" })).not.toHaveAttribute(
      "aria-current",
    );
  });
});
