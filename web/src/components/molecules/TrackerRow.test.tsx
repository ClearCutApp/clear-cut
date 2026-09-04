import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { TrackerItem } from "../../api/client";
import { TrackerRow } from "./TrackerRow";
import trackerFixture from "../../fixtures/tracker.json";

const ferrariItem = trackerFixture[0] as TrackerItem;

// The verified wire truth (CHECKPOINTS.md CP-054, D53's "Active" section):
// the seeded continuity tracker item -- the one with no rights claim behind
// it -- carries `contact`, `litigation_posture` and `note` all as empty
// strings, never null. Since D60 the committed fixture is the captured mock
// body itself, so its third row is that item.
const emptyValueItem = trackerFixture[2] as TrackerItem;

function noop(): void {
  // unused callback slot for props this test does not exercise
}

describe("TrackerRow", () => {
  it("renders the state badge, contact, document, posture, and note", () => {
    render(
      <TrackerRow
        item={ferrariItem}
        onStateChange={noop}
        onDraftEmail={noop}
        onNotify={noop}
      />,
    );

    expect(screen.getByTestId("state-badge")).toHaveTextContent("BLOCKED");
    expect(screen.getByText(/legal@ferrari\.example/)).toBeInTheDocument();
    expect(
      screen.getByText(/Trademark Clearance Form/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/cease-and-desist letters on file/),
    ).toBeInTheDocument();
  });

  it("renders the empty-contact row readably, with no undefined and no dangling colon", () => {
    render(
      <TrackerRow
        item={emptyValueItem}
        onStateChange={noop}
        onDraftEmail={noop}
        onNotify={noop}
      />,
    );

    const row = screen.getByTestId("tracker-row");
    expect(row.textContent).not.toMatch(/undefined/);
    expect(row.textContent).not.toMatch(/Contact:\s*(<|$)/);
    expect(screen.getByText(/no contact on file/i)).toBeInTheDocument();
    expect(
      screen.getByText(/no litigation history on file/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/no notes/i)).toBeInTheDocument();
  });

  it("calls onStateChange with the item id and new state when the select changes", () => {
    const onStateChange = vi.fn();
    render(
      <TrackerRow
        item={ferrariItem}
        onStateChange={onStateChange}
        onDraftEmail={noop}
        onNotify={noop}
      />,
    );

    fireEvent.change(screen.getByLabelText(/state/i), {
      target: { value: "IN_PROGRESS" },
    });

    expect(onStateChange).toHaveBeenCalledWith("EVT-001", "IN_PROGRESS");
  });

  it("calls onDraftEmail and onNotify with the item id when their buttons are clicked", () => {
    const onDraftEmail = vi.fn();
    const onNotify = vi.fn();
    render(
      <TrackerRow
        item={ferrariItem}
        onStateChange={noop}
        onDraftEmail={onDraftEmail}
        onNotify={onNotify}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /draft email/i }));
    fireEvent.click(screen.getByRole("button", { name: /notify/i }));

    expect(onDraftEmail).toHaveBeenCalledWith("EVT-001");
    expect(onNotify).toHaveBeenCalledWith("EVT-001");
  });

  it("shows only the two implemented actions, no menu entry for the other two", () => {
    render(
      <TrackerRow
        item={ferrariItem}
        onStateChange={noop}
        onDraftEmail={noop}
        onNotify={noop}
      />,
    );

    expect(
      screen.queryByRole("button", { name: /generate document/i }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: /stakeholder link/i }),
    ).toBeNull();
  });

  it("renders the returned draft email text when present", () => {
    const drafted: TrackerItem = { ...ferrariItem, draft_email: "Dear Ferrari S.p.A., ..." };
    render(
      <TrackerRow
        item={drafted}
        onStateChange={noop}
        onDraftEmail={noop}
        onNotify={noop}
      />,
    );

    expect(screen.getByText(/Dear Ferrari S\.p\.A\./)).toBeInTheDocument();
  });

  it("disables the state select and the two action buttons while pending", () => {
    render(
      <TrackerRow
        item={ferrariItem}
        onStateChange={noop}
        onDraftEmail={noop}
        onNotify={noop}
        pending
      />,
    );

    expect(screen.getByLabelText(/^state$/i)).toBeDisabled();
    expect(
      screen.getByRole("button", { name: /draft email/i }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: /notify/i })).toBeDisabled();
  });

  it("leaves the select and buttons enabled when not pending", () => {
    render(
      <TrackerRow
        item={ferrariItem}
        onStateChange={noop}
        onDraftEmail={noop}
        onNotify={noop}
      />,
    );

    expect(screen.getByLabelText(/^state$/i)).toBeEnabled();
    expect(screen.getByRole("button", { name: /draft email/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /notify/i })).toBeEnabled();
  });
});
