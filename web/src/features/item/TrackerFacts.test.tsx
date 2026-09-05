import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TRACKER_FIXTURE } from "../../fixtures";
import { TrackerFacts } from "./TrackerFacts";


describe("TrackerFacts", () => {
  it("shows the state, contact, posture, note and version of the item", () => {
    const { container } = render(
      <TrackerFacts item={TRACKER_FIXTURE[0]} pending={false} onStateChange={vi.fn()} />,
    );

    const select = screen.getByLabelText("State");
    expect(select).toHaveValue("BLOCKED");
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual([
      "BLOCKED",
      "IN_PROGRESS",
      "CLEARED",
    ]);
    expect(screen.getByText("legal@ferrari.example")).toBeInTheDocument();
    expect(
      screen.getByText("cease-and-desist letters on file for unlicensed film placements"),
    ).toBeInTheDocument();
    expect(screen.getByText("no notes")).toBeInTheDocument();
    expect(screen.getByText(/Version 1, updated/)).toBeInTheDocument();
    expect(container.querySelector("time")).toHaveAttribute(
      "datetime",
      TRACKER_FIXTURE[0].updated_at,
    );
  });

  it("words the empty fields rather than leaving them blank", () => {
    render(<TrackerFacts item={TRACKER_FIXTURE[2]} pending={false} onStateChange={vi.fn()} />);

    expect(screen.getByText("no contact on file")).toBeInTheDocument();
    expect(screen.getByText("no litigation history on file")).toBeInTheDocument();
    expect(screen.getByText("no notes")).toBeInTheDocument();
  });

  it("reports the chosen state and lets every transition through", () => {
    const onStateChange = vi.fn();
    render(
      <TrackerFacts item={TRACKER_FIXTURE[0]} pending={false} onStateChange={onStateChange} />,
    );

    fireEvent.change(screen.getByLabelText("State"), { target: { value: "CLEARED" } });

    expect(onStateChange).toHaveBeenCalledWith("CLEARED");
  });

  it("shows the draft email verbatim once one exists", () => {
    const drafted = {
      ...TRACKER_FIXTURE[0],
      draft_email: "Subject: Rights clearance request\n\nDear Ferrari S.p.A.,",
    };
    render(<TrackerFacts item={drafted} pending={false} onStateChange={vi.fn()} />);

    const draft = screen.getByText(/Subject: Rights clearance request/);
    expect(draft.tagName).toBe("PRE");
    expect(draft).toHaveTextContent("Dear Ferrari S.p.A.,");
    expect(screen.getByText("Draft email")).toBeInTheDocument();
  });

  it("shows no draft email section before one is generated", () => {
    render(<TrackerFacts item={TRACKER_FIXTURE[0]} pending={false} onStateChange={vi.fn()} />);

    expect(screen.queryByText("Draft email")).toBeNull();
  });

  it("disables the state select while a mutation is in flight", () => {
    render(<TrackerFacts item={TRACKER_FIXTURE[0]} pending onStateChange={vi.fn()} />);

    expect(screen.getByLabelText("State")).toBeDisabled();
  });
});
