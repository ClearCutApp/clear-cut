import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import * as api from "../api/client";
import { ReportsView } from "./ReportsView";

let projectId = "one";
vi.mock("../state/ProjectContext", () => ({ useProject: () => ({ projectId }) }));
afterEach(() => { vi.restoreAllMocks(); projectId = "one"; });
const counts: api.ClearanceCounts = { total_retained: 2, confirmed_cleared: 1, needs_review: 1, blocked: 0, in_progress: 0, present: 2, not_detected: 0, unknown_binding: 0, confirmed_cleared_percent: 50 };
const snapshot: api.ReportSnapshotContext = { analysis_id: "analysis", revision_id: "revision-3", expected_generation: "generation", expected_epoch: 7, counts };
const report = { report_id: "saved", revision_id: "revision-3", counts, created_at: "2026-09-06T12:00:00Z", language: "en" } as api.ClearanceReport;

it("sends the displayed fixed snapshot and preserves saved reports after a conflict", async () => {
  vi.spyOn(api, "listReports").mockResolvedValue({ reports: [report], next_before: null });
  vi.spyOn(api, "getReportContext").mockResolvedValue({ configured: true, snapshot });
  const create = vi.spyOn(api, "createReport").mockRejectedValue(new api.ApiError(409, "changed"));
  render(<MemoryRouter><ReportsView /></MemoryRouter>);
  fireEvent.click(await screen.findByRole("button", { name: "Save report" }));
  await screen.findByRole("alert");
  expect(create).toHaveBeenCalledWith("one", snapshot, "en");
  expect(screen.queryByRole("button", { name: "Save report" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "PDF" })).toBeInTheDocument();
});

it("does not invent report creation in the isolated demo", async () => {
  vi.spyOn(api, "listReports").mockResolvedValue({ reports: [], next_before: null });
  vi.spyOn(api, "getReportContext").mockResolvedValue({ configured: false, snapshot: null });
  render(<MemoryRouter><ReportsView /></MemoryRouter>);
  await screen.findByText(/Saved revision reports are unavailable/);
  expect(screen.queryByRole("button", { name: "Save report" })).not.toBeInTheDocument();
});

it("ignores a pending report creation after the project changes", async () => {
  vi.spyOn(api, "listReports").mockResolvedValue({ reports: [], next_before: null });
  vi.spyOn(api, "getReportContext").mockResolvedValue({ configured: true, snapshot });
  let resolve!: (report: api.ClearanceReport) => void;
  vi.spyOn(api, "createReport").mockReturnValue(new Promise(done => { resolve = done; }));
  const view = render(<MemoryRouter><ReportsView /></MemoryRouter>);
  fireEvent.click(await screen.findByRole("button", { name: "Save report" }));
  projectId = "two";
  view.rerender(<MemoryRouter><ReportsView /></MemoryRouter>);
  await waitFor(() => expect(api.getReportContext).toHaveBeenCalledWith("two"));
  await act(async () => resolve(report));
  expect(screen.queryByRole("button", { name: "PDF" })).not.toBeInTheDocument();
});
