import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import * as api from "../api/client";
import { ActivityView } from "./ActivityView";

let projectId = "one";
vi.mock("../state/ProjectContext", () => ({ useProject: () => ({ projectId }) }));
afterEach(() => { vi.restoreAllMocks(); projectId = "one"; });

it("shows captured analysis counts and preserves the recorded revision label", async () => {
  vi.spyOn(api, "getProjectActivity").mockResolvedValue({
    configured: true, next_before: null,
    events: [{ event_id: "event", kind: "clearance_changed", occurred_at: "2026-09-06T12:00:00Z", source_version: 2, payload: { item_id: "EVT-001", needs_review: true } }],
    trends: [{ event_id: "analysis", kind: "analysis_published", occurred_at: "2026-09-06T12:00:00Z", source_version: 1, payload: { revision_id: "revision-1", counts: { confirmed_cleared: 2, total_retained: 5 } } }],
  });
  render(<ActivityView />);
  await screen.findByText("revision-1");
  expect(screen.getByText("2/5 confirmed")).toBeInTheDocument();
  expect(screen.getByText("Needs review")).toBeInTheDocument();
});

it("ignores private activity arriving after a project switch", async () => {
  let resolve!: (page: api.ActivityPage) => void;
  vi.spyOn(api, "getProjectActivity")
    .mockReturnValueOnce(new Promise(done => { resolve = done; }))
    .mockResolvedValueOnce({ configured: true, events: [], trends: [], next_before: null });
  const view = render(<ActivityView />);
  projectId = "two"; view.rerender(<ActivityView />);
  await screen.findByText("No projected activity yet.");
  await act(async () => resolve({ configured: true, events: [{
    event_id: "private", kind: "revision_saved", occurred_at: "2026-09-06T12:00:00Z",
    source_version: 1, payload: { revision_id: "private-revision" },
  }], trends: [], next_before: null }));
  expect(screen.queryByText(/private-revision/)).not.toBeInTheDocument();
});
