import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../../api/client";
import { ItemHistory } from "./ItemHistory";

afterEach(() => vi.restoreAllMocks());

describe("clearance history", () => {
  it("loads only when requested and displays the recorded actor and version", async () => {
    const load = vi.spyOn(api, "listTrackerItemHistory").mockResolvedValue([{
      event_id: "event", actor: "producer", version: 2, previous_version: 1,
      at: "2026-09-06T10:00:00Z", item: { state: "IN_PROGRESS" } as api.TrackerItem,
    }]);
    render(<ItemHistory projectId="project" itemId="item" version={2} />);
    expect(load).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Clearance history" }));
    expect(await screen.findByText("Version 2 · IN_PROGRESS")).toBeInTheDocument();
    expect(load).toHaveBeenCalledWith("project", "item", undefined);
    expect(screen.getByText(/producer/)).toBeInTheDocument();
  });

  it("ignores a late history response after the selected item changes", async () => {
    let resolve!: (events: api.TrackerAuditEvent[]) => void;
    vi.spyOn(api, "listTrackerItemHistory").mockReturnValue(new Promise((done) => { resolve = done; }));
    const view = render(<ItemHistory projectId="one" itemId="item" version={1} />);
    fireEvent.click(screen.getByRole("button", { name: "Clearance history" }));
    view.rerender(<ItemHistory projectId="two" itemId="other" version={1} />);
    await act(async () => resolve([{
      event_id: "private", actor: "private actor", version: 2, previous_version: 1,
      at: "now", item: { state: "CLEARED" } as api.TrackerItem,
    }]));
    expect(screen.queryByText(/private actor/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Clearance history" })).toHaveAttribute("aria-expanded", "false");
  });
});
